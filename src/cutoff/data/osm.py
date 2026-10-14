"""Pre-event OpenStreetMap extraction through ohsome (v2, then v1/cache)."""
from __future__ import annotations

import hashlib
import io
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import box, mapping

from cutoff.runctx import RunContext

STAGE = "osm"
LAYERS = {
    "roads": (
        "highway in (motorway, trunk, primary, secondary, tertiary, unclassified, residential, service, track, "
        "path, footway, steps, bridleway, motorway_link, trunk_link, primary_link, secondary_link, tertiary_link) "
        "and type:way"
    ),
    "buildings": "building=* and geometry:polygon",
    "places": "place in (city, town, village, hamlet, isolated_dwelling, locality) and geometry:point",
    "health": (
        "(amenity in (hospital, clinic, doctors) or healthcare in (hospital, clinic, centre, doctor) or healthcare=*)"
    ),
}
ROAD_VALUES = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
}
TRAIL_VALUES = {"path", "footway", "steps", "bridleway"}
OUTPUT_COLUMNS = {
    "roads": ["osm_id", "highway", "tier", "bridge", "name", "layer", "tunnel", "geometry"],
    "buildings": ["osm_id", "geometry"],
    "places": ["osm_id", "place", "name", "geometry"],
    "health": ["osm_id", "kind", "name", "geometry"],
}


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def assert_pre_event(snapshot_iso: str, event: datetime) -> None:
    """Reject non-specific and non-pre-event OSM snapshots before any request."""
    if snapshot_iso.strip().lower() == "latest":
        raise ValueError("OSM snapshot must be an explicit pre-event timestamp; 'latest' is forbidden")
    try:
        snapshot = _utc(snapshot_iso)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid OSM snapshot timestamp: {snapshot_iso!r}") from exc
    if snapshot >= _utc(event):
        raise ValueError("OSM snapshot must be strictly before the event")


def _osm_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("osm", cfg)


def _tag_dict(value: Any) -> dict[str, Any]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "as_py"):
        value = value.as_py()
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _first_column(frame: pd.DataFrame, names: tuple[str, ...]) -> pd.Series:
    for name in names:
        if name in frame:
            return frame[name]
    return pd.Series([None] * len(frame), index=frame.index, dtype="object")


def _health_kind(tags: dict[str, Any]) -> str:
    raw = str(tags.get("healthcare") or tags.get("amenity") or "clinic").lower()
    if raw in {"doctor", "doctors"}:
        return "doctors"
    if raw in {"centre", "center", "health_post", "health post"}:
        return "health_post"
    return raw if raw in {"hospital", "clinic"} else "clinic"


def parse_layer(raw: gpd.GeoDataFrame, layer: str) -> gpd.GeoDataFrame:
    """Flatten ohsome tags and derive the frozen vector-contract fields."""
    if layer not in LAYERS:
        raise ValueError(f"unknown OSM layer: {layer}")
    frame = raw.copy()
    tags = frame["tags"].map(_tag_dict) if "tags" in frame else pd.Series([{}] * len(frame), index=frame.index)
    ids = _first_column(frame, ("@osmId", "osm_id", "osmId", "id", "@id"))
    types = _first_column(frame, ("@osmType", "osm_type", "type", "@type"))

    def osm_id(i: Any, typ: Any) -> str:
        text = str(i)
        if "/" in text:
            return text
        prefix = str(typ).lower() if typ is not None else ""
        prefix = {"n": "node", "w": "way", "r": "relation"}.get(prefix, prefix)
        return f"{prefix}/{text}" if prefix in {"node", "way", "relation"} else text

    out = gpd.GeoDataFrame({"osm_id": [osm_id(i, t) for i, t in zip(ids, types)]},
                           geometry=frame.geometry, crs=frame.crs or 4326)
    if layer == "roads":
        out["highway"] = tags.map(lambda t: t.get("highway", ""))
        out["tier"] = out.highway.map(lambda h: "road" if h in ROAD_VALUES else "trail" if h in TRAIL_VALUES else "track")
        out["bridge"] = tags.map(lambda t: str(t.get("bridge", "no")).lower() not in {"", "no", "none", "false", "0"})
        out["name"] = tags.map(lambda t: t.get("name") or "")
        out["layer"] = tags.map(lambda t: str(t.get("layer") or "0"))
        out["tunnel"] = tags.map(lambda t: str(t.get("tunnel", "no")).lower() not in {"", "no", "none", "false", "0"})
    elif layer == "places":
        out["place"] = tags.map(lambda t: t.get("place", ""))
        out["name"] = tags.map(lambda t: t.get("name") or "")
    elif layer == "health":
        out["kind"] = tags.map(_health_kind)
        out["name"] = tags.map(lambda t: t.get("name") or "")
        out.geometry = out.geometry.map(lambda geom: geom.centroid if geom is not None and geom.geom_type != "Point" else geom)

    out = out.loc[out.geometry.notna() & ~out.geometry.is_empty].copy()
    if layer in {"roads", "buildings"} and len(out):
        out = out.explode(index_parts=False, ignore_index=True)
    if layer == "roads":
        # A highway-tagged area is not a routing centreline. Polygon.coords
        # raises in network noding (observed in the real south AOI).
        out = out.loc[out.geom_type.eq("LineString")].copy()
    return out[OUTPUT_COLUMNS[layer]]


def _read_v2(content: bytes) -> gpd.GeoDataFrame:
    return gpd.read_parquet(io.BytesIO(content), to_pandas_kwargs={"maps_as_pydicts": "strict"})


def _request_v2(aoi, layer: str, snapshot_iso: str, cfg: dict[str, Any]) -> gpd.GeoDataFrame:
    base = str(cfg.get("api_v2", "https://api.heigit.org/ohsome-api/v2")).rstrip("/")
    key = os.environ.get("OHSOME_API_KEY", "")
    if not key:
        raise RuntimeError("OHSOME_API_KEY is required for ohsome API v2")
    payload = {"aoi": mapping(aoi), "filter": LAYERS[layer], "time": snapshot_iso, "clip": False}
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = httpx.post(f"{base}/extraction/features.parquet", json=payload,
                                  headers={"authorization": key}, timeout=240.0)
            response.raise_for_status()
            result = _read_v2(response.content)
            result.attrs["osm_api"] = "v2"
            return result
        except (httpx.HTTPError, OSError, ValueError) as exc:
            last = exc
            if attempt < 2:
                retry_after = 0.0
                if isinstance(exc, httpx.HTTPStatusError):
                    try:
                        retry_after = float(exc.response.headers.get("retry-after", 0))
                    except ValueError:
                        retry_after = 0.0
                    if exc.response.status_code == 429:
                        # HeiGIT uses a sliding 60-second extraction limit. Short
                        # retries can exhaust every attempt before it clears.
                        retry_after = max(retry_after, 60.0)
                time.sleep(max(retry_after, 5.0 * (2 ** attempt)))
    raise RuntimeError(f"ohsome v2 failed after 3 attempts: {last}") from last


def _request_v1(aoi, layer: str, snapshot_iso: str, cfg: dict[str, Any]) -> gpd.GeoDataFrame:
    base = str(cfg.get("api_v1", "https://api.ohsome.org/v1")).rstrip("/")
    data = {"bboxes": ",".join(map(str, aoi.bounds)), "filter": LAYERS[layer], "time": snapshot_iso,
            "properties": "tags"}
    response = httpx.post(f"{base}/elements/geometry", data=data, timeout=120.0)
    response.raise_for_status()
    result = gpd.GeoDataFrame.from_features(response.json().get("features", []), crs=4326)
    result.attrs["osm_api"] = "v1"
    return result


def fetch_layer(aoi_wgs84, layer: str, snapshot_iso: str, cfg: dict[str, Any]) -> gpd.GeoDataFrame:
    """Fetch one EPSG:4326 tile, trying v2 three times and then v1."""
    if snapshot_iso.strip().lower() == "latest":
        raise ValueError("time='latest' is forbidden for pre-event OSM")
    settings = _osm_cfg(cfg)
    try:
        raw = _request_v2(aoi_wgs84, layer, snapshot_iso, settings)
    except Exception as v2_error:  # noqa: BLE001 - every v2 failure must trigger the documented v1 fallback
        try:
            raw = _request_v1(aoi_wgs84, layer, snapshot_iso, settings)
        except Exception as v1_error:
            raise RuntimeError(f"ohsome v2 and v1 failed ({v2_error}; {v1_error})") from v1_error
    api = raw.attrs.get("osm_api", "v2")
    out = parse_layer(raw, layer)
    out.attrs["osm_api"] = api
    return out.to_crs(4326)


def _tiles(bounds: tuple[float, float, float, float], size: float):
    west, south, east, north = bounds
    x = west
    while x < east:
        y = south
        while y < north:
            yield box(x, y, min(x + size, east), min(y + size, north))
            y += size
        x += size


def _access_aoi(ctx: RunContext):
    aoi = gpd.GeoSeries([box(*ctx.aoi_bbox)], crs=4326)
    metres = float(ctx.cfg.get("access", {}).get("access_buffer_km", 15)) * 1000
    return aoi.to_crs(ctx.grid.crs).buffer(metres).to_crs(4326).iloc[0]


def _snapshot_slug(snapshot_iso: str) -> str:
    """Derive a filesystem-safe slug from the OSM snapshot ISO timestamp.

    The slug is included in the cache directory so that cached parquet files
    from one snapshot date can never silently bleed into a run that uses a
    different snapshot date (fixes #25).
    """
    return _utc(snapshot_iso).isoformat().replace("+00:00", "Z").replace(":", "")


def _cache_dir(ctx: RunContext) -> Path:
    from cutoff.data.s1_acquire import cache_root, grid_hash

    # A grid alone does not identify the buffered routing query. Bind the
    # requested AOI, routing coverage and filters as well as the exact date.
    profile = {
        "aoi_bbox": list(ctx.aoi_bbox),
        "access_buffer_km": float(ctx.cfg.get("access", {}).get("access_buffer_km", 15)),
        "filters": LAYERS,
    }
    digest = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()[:16]
    return cache_root(ctx) / "osm" / grid_hash(ctx.grid) / _snapshot_slug(ctx.osm_snapshot) / digest


def stage_osm(ctx: RunContext) -> dict:
    """Write the four contract OSM layers in the run grid CRS."""
    assert_pre_event(ctx.osm_snapshot, ctx.event_datetime)
    settings = _osm_cfg(ctx.cfg)
    tile_deg = float(settings.get("tile_deg", 0.5))
    base_aoi = box(*ctx.aoi_bbox)
    access_aoi = _access_aoi(ctx)
    counts: dict[str, int] = {}
    apis: set[str] = set()
    cache_dir = _cache_dir(ctx)
    cache_dir.mkdir(parents=True, exist_ok=True)

    for layer in LAYERS:
        cache_path = cache_dir / f"{layer}.parquet"
        try:
            if ctx.mode == "cached":
                raise RuntimeError("cached mode does not make OSM requests")
            extent = base_aoi if layer == "buildings" else access_aoi
            pieces = []
            for tile in _tiles(extent.bounds, tile_deg):
                part = fetch_layer(tile.intersection(extent), layer, ctx.osm_snapshot, ctx.cfg)
                apis.add(part.attrs.get("osm_api", "v2"))
                pieces.append(part)
                delay = float(settings.get("request_delay_s", 4.1))
                if delay > 0:
                    time.sleep(delay)
            frame = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs=4326)
            frame = frame.drop_duplicates("osm_id").reset_index(drop=True)
            frame.to_parquet(cache_path)
        except Exception as exc:
            if not cache_path.exists():
                raise
            ctx.warn(STAGE, f"ohsome unavailable for {layer}; using matching cached pre-event OSM: {exc}")
            frame = gpd.read_parquet(cache_path)
            apis.add("cache")
        if layer == "roads":
            # Apply the same contract to dated caches created before this fix.
            frame = frame.loc[frame.geom_type.eq("LineString")].copy()
        frame = frame.to_crs(ctx.grid.crs)
        frame.to_file(ctx.path(f"osm_{layer}"), driver="GPKG")
        counts[layer] = len(frame)
        ctx.log(STAGE, event="layer", layer=layer, count=len(frame))

    osm_api = "cache" if "cache" in apis else "v1" if "v1" in apis else "v2"
    return {"osm_snapshot": ctx.osm_snapshot, "osm_api": osm_api, "counts": counts}


__all__ = ["assert_pre_event", "fetch_layer", "parse_layer", "stage_osm"]

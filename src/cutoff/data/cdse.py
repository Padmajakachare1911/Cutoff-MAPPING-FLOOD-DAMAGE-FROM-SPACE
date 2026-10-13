"""CDSE STAC search for Sentinel-1 GRD scenes (Owner: P1, task P1.1).

`search_s1` queries https://stac.dataspace.copernicus.eu/v1 (collection `sentinel-1-grd`, no auth) and
turns each item into a `Scene`. `scenes_from_items` does the item -> Scene conversion on raw item dicts,
so the pair-selection tests run offline on tests/fixtures/stac_trishuli_s1.json.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from pyproj import Transformer
from shapely import transform as shp_transform
from shapely.geometry import box, shape

from cutoff.geo.grid import utm_epsg

S1_COLLECTION = "sentinel-1-grd"
_ID_TIMES = re.compile(r"_(\d{8}T\d{6})_(\d{8}T\d{6})_")
_SEGMENT_DEG = 0.01  # densify lon/lat edges before projecting to UTM


@dataclass(frozen=True)
class Scene:
    id: str
    datetime: datetime
    start: datetime
    end: datetime
    rel_orbit: int
    direction: str                      # "ascending" | "descending"
    platform: str                       # "sentinel-1c" | "sentinel-1d" | ...
    pols: tuple[str, ...]
    coverage: float                     # fraction of the AOI covered by the item footprint (computed in UTM)
    assets: dict[str, str]              # vv, vh, Product, schema-calibration-vv, ...
    product_uuid: str | None = None     # OData id (full/SNAP download path, P1.7)

    def summary(self) -> dict:
        """JSON-safe description used in pairs.json and the stage return dict."""
        return {"id": self.id, "datetime": iso(self.datetime), "platform": self.platform,
                "rel_orbit": self.rel_orbit, "orbit_direction": self.direction,
                "start": iso(self.start), "end": iso(self.end), "coverage": round(self.coverage, 4)}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def product_stem(item_id: str) -> str:
    """Product name without the 4-char product unique id and the `_COG` suffix: two items with the same
    stem are the same acquisition (e.g. reprocessed)."""
    stem = item_id[:-4] if item_id.endswith("_COG") else item_id
    return stem.rsplit("_", 1)[0]


def _times_from_id(item_id: str) -> tuple[datetime, datetime]:
    m = _ID_TIMES.search(item_id)
    if not m:
        raise ValueError(f"no start/stop timestamps in item id {item_id!r}")
    f = lambda s: datetime.strptime(s, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    return f(m.group(1)), f(m.group(2))


def aoi_coverage(footprint_geojson: dict, aoi_bbox: tuple[float, float, float, float]) -> float:
    """Fraction of the AOI bbox (W, S, E, N degrees) inside the footprint, measured in the AOI's UTM zone."""
    w, s, e, n = aoi_bbox
    t = Transformer.from_crs(4326, utm_epsg((w + e) / 2, (s + n) / 2), always_xy=True)
    to_utm = lambda geom: shp_transform(geom.segmentize(_SEGMENT_DEG), lambda xy: _xy(t, xy))
    aoi = to_utm(box(w, s, e, n))
    foot = to_utm(shape(footprint_geojson))
    return float(foot.intersection(aoi).area / aoi.area) if aoi.area > 0 else 0.0


def _xy(t: Transformer, xy):
    import numpy as np

    x, y = t.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([x, y])


def scene_from_item(item: dict, aoi_bbox) -> Scene:
    p = item["properties"]
    if p.get("start_datetime") and p.get("end_datetime"):
        start, end = parse_dt(p["start_datetime"]), parse_dt(p["end_datetime"])
    else:
        start, end = _times_from_id(item["id"])
    dt = parse_dt(p["datetime"]) if p.get("datetime") else start
    assets = {k: a["href"] for k, a in item.get("assets", {}).items()
              if "thumbnail" not in k and "thumbnail" not in a.get("roles", [])}
    return Scene(id=item["id"], datetime=dt, start=start, end=end,
                 rel_orbit=int(p["sat:relative_orbit"]), direction=str(p["sat:orbit_state"]).lower(),
                 platform=str(p.get("platform", "")).lower(), pols=tuple(p.get("sar:polarizations", ())),
                 coverage=aoi_coverage(item["geometry"], aoi_bbox), assets=assets,
                 product_uuid=(p.get("_private") or {}).get("product_uuid"))


def scenes_from_items(items: list[dict], aoi_bbox) -> list[Scene]:
    """Raw STAC item dicts -> Scenes (newest first). Items of the same product stem are deduped,
    keeping the most recently processed one. Non-IW items are skipped (every backend requests IW)."""
    best: dict[str, dict] = {}
    for it in items:
        mode = it["properties"].get("sar:instrument_mode")
        if mode and mode != "IW":
            continue
        key = product_stem(it["id"])
        prev = best.get(key)
        stamp = lambda x: x["properties"].get("processing:datetime") or x["properties"].get("updated") or ""
        if prev is None or stamp(it) >= stamp(prev):
            best[key] = it
    scenes = [scene_from_item(it, aoi_bbox) for it in best.values()]
    return sorted(scenes, key=lambda s: s.datetime, reverse=True)


def search_items(bbox, start: datetime, end: datetime, stac_url: str,
                 collection: str = S1_COLLECTION, limit: int = 100) -> list[dict]:
    """Raw item dicts from a STAC search (no auth)."""
    from pystac_client import Client

    client = Client.open(stac_url)
    search = client.search(collections=[collection], bbox=list(bbox),
                           datetime=f"{iso(start)}/{iso(end)}", limit=limit)
    return [it.to_dict() for it in search.items()]


def search_s1(bbox, start: datetime, end: datetime, stac_url: str) -> list[Scene]:
    """Sentinel-1 GRD scenes intersecting bbox (W, S, E, N) between start and end, newest first."""
    return scenes_from_items(search_items(bbox, start, end, stac_url), bbox)

"""Derive reportable settlements and road-access targets from pre-event OSM."""
from __future__ import annotations

import hashlib

import geopandas as gpd
from shapely.geometry import box
from shapely.ops import unary_union

from cutoff.runctx import RunContext

STAGE = "settlements"


def _stable_id(prefix: str, point) -> str:
    key = f"{point.x:.1f},{point.y:.1f}"
    return f"{prefix}{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def _empty_settlements(crs) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"sid": [], "name": [], "source": [], "n_buildings": []}, geometry=[], crs=crs)


def derive_settlements(places: gpd.GeoDataFrame, buildings: gpd.GeoDataFrame, aoi) -> gpd.GeoDataFrame:
    """Combine in-AOI place points with unsuppressed clusters of at least five buildings."""
    places_in = places.loc[places.geometry.within(aoi) | places.geometry.touches(aoi)].copy()
    centroids = buildings.geometry.centroid
    rows = []
    for _, place in places_in.iterrows():
        n_buildings = int(centroids.distance(place.geometry).le(150).sum())
        rows.append({"geometry": place.geometry, "name": place.get("name") or "Unnamed place",
                     "source": "osm_place", "n_buildings": n_buildings})

    if len(centroids):
        merged = unary_union([point.buffer(40) for point in centroids])
        components = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        for component in components:
            members = centroids[centroids.within(component) | centroids.touches(component)]
            if len(members) < 5:
                continue
            point = unary_union(list(members)).centroid
            if not (point.within(aoi) or point.touches(aoi)):
                continue
            if len(places_in) and places_in.geometry.distance(point).le(300).any():
                continue
            suffix = ""
            if len(places):
                distances = places.geometry.distance(point)
                nearest = distances.idxmin()
                if distances.loc[nearest] <= 2000:
                    near_name = places.loc[nearest].get("name") or ""
                    suffix = f" near {near_name}" if near_name else ""
            # A cluster mean can fall in a river or an empty courtyard. Keep
            # clustering/suppression based on the mean, but anchor its marker
            # inside a real member footprint. This is a representative location,
            # not a surveyed settlement boundary or a claim of inundation.
            anchors = buildings.loc[members.index].geometry.representative_point()
            anchors = anchors[anchors.within(aoi) | anchors.touches(aoi)]
            if anchors.empty:
                continue
            point = anchors.loc[anchors.distance(point).idxmin()]
            rows.append({"geometry": point, "name": f"Unnamed settlement ({len(members)} bldgs){suffix}",
                         "source": "building_cluster", "n_buildings": len(members)})

    if not rows:
        return _empty_settlements(places.crs or buildings.crs)
    out = gpd.GeoDataFrame(rows, geometry="geometry", crs=places.crs or buildings.crs)
    out.insert(0, "sid", out.geometry.map(lambda point: _stable_id("S", point)))
    return out[["sid", "name", "source", "n_buildings", "geometry"]]


def derive_targets(places: gpd.GeoDataFrame, health: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Use health facilities and all buffered-extent towns/cities as destinations."""
    records = []
    for _, row in health.iterrows():
        records.append({"geometry": row.geometry, "name": row.get("name") or "Unnamed health facility",
                        "kind": row.get("kind") or "clinic"})
    for _, row in places.loc[places["place"].isin(("town", "city"))].iterrows():
        records.append({"geometry": row.geometry, "name": row.get("name") or f"Unnamed {row['place']}",
                        "kind": row["place"]})
    if not records:
        return gpd.GeoDataFrame({"tid": [], "name": [], "kind": []}, geometry=[], crs=places.crs or health.crs)
    out = gpd.GeoDataFrame(records, geometry="geometry", crs=places.crs or health.crs)
    out.insert(0, "tid", out.geometry.map(lambda point: _stable_id("T", point)))
    return out.drop_duplicates("tid")[["tid", "name", "kind", "geometry"]].reset_index(drop=True)


def stage_settlements(ctx: RunContext) -> dict:
    """Write settlements within the AOI and targets from the full access extent."""
    places = gpd.read_file(ctx.path("osm_places"))
    buildings = gpd.read_file(ctx.path("osm_buildings"))
    health = gpd.read_file(ctx.path("osm_health"))
    aoi = gpd.GeoSeries([box(*ctx.aoi_bbox)], crs=4326).to_crs(ctx.grid.crs).iloc[0]
    settlements = derive_settlements(places, buildings, aoi)
    targets = derive_targets(places, health)
    settlements.to_file(ctx.path("settlements"), driver="GPKG")
    targets.to_file(ctx.path("targets"), driver="GPKG")
    if targets.empty:
        ctx.warn(STAGE, "no hospital/town within AOI + 15 km in pre-event OSM")
    ctx.log(STAGE, event="complete", n_settlements=len(settlements), n_targets=len(targets))
    return {"n_settlements": len(settlements), "n_targets": len(targets)}


__all__ = ["derive_settlements", "derive_targets", "stage_settlements"]

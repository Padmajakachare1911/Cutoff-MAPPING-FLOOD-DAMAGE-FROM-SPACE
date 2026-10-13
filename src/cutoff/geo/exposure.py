"""Intersect mapped hazard with pre-event OSM assets to quantify exposure."""
from __future__ import annotations

import geopandas as gpd
import pandas as pd

from cutoff.contracts import HAZARD_CLASS_NAMES
from cutoff.runctx import RunContext

STAGE = "exposure"
PRIORITY = (1, 4, 3, 2)


def _hazard_unions(hazard: gpd.GeoDataFrame) -> dict[int, object]:
    return {code: hazard.loc[hazard["class"] == code].geometry.union_all()
            for code in PRIORITY if (hazard["class"] == code).any()}


def exposed_buildings(buildings: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return each intersecting building once, assigned to its highest-priority touched class."""
    unions = _hazard_unions(hazard)
    rows = []
    for _, building in buildings.iterrows():
        code = next((value for value in PRIORITY if value in unions and building.geometry.intersects(unions[value])), None)
        if code is not None:
            row = building.to_dict()
            row["hazard_class"] = code
            rows.append(row)
    if not rows:
        return gpd.GeoDataFrame({"osm_id": [], "hazard_class": []}, geometry=[], crs=buildings.crs)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=buildings.crs)


def exposed_roads(roads: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Return non-empty road fragments within each hazard class and their projected length."""
    unions = _hazard_unions(hazard)
    frames = []
    for code in PRIORITY:
        if code not in unions:
            continue
        part = roads.copy()
        part.geometry = part.geometry.intersection(unions[code])
        part = part.loc[part.geometry.map(lambda geom: geom is not None and not geom.is_empty)].copy()
        if part.empty:
            continue
        part = part.explode(index_parts=False, ignore_index=True)
        part["hazard_class"] = code
        part["length_m"] = part.length
        frames.append(part)
    if not frames:
        return gpd.GeoDataFrame({"osm_id": [], "hazard_class": [], "length_m": []}, geometry=[], crs=roads.crs)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=roads.crs)


def exposed_bridge_counts(roads: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame) -> dict[str, int]:
    """Count bridge ways within 15 m of hazard, assigning each to its highest-priority class."""
    bridges = roads.loc[roads["bridge"].astype(bool)]
    unions = _hazard_unions(hazard)
    counts = {HAZARD_CLASS_NAMES[code]: 0 for code in PRIORITY}
    for geom in bridges.geometry:
        code = next((value for value in PRIORITY if value in unions and geom.distance(unions[value]) <= 15), None)
        if code is not None:
            counts[HAZARD_CLASS_NAMES[code]] += 1
    return counts


def stage_exposure(ctx: RunContext) -> dict:
    """Write exposed building footprints and road fragments."""
    hazard = gpd.read_file(ctx.path("hazard"))
    buildings = gpd.read_file(ctx.path("osm_buildings"))
    roads = gpd.read_file(ctx.path("osm_roads"))
    out_buildings = exposed_buildings(buildings, hazard)
    out_roads = exposed_roads(roads, hazard)
    out_buildings.to_file(ctx.path("exposure_buildings"), driver="GPKG")
    out_roads[["osm_id", "hazard_class", "length_m", "geometry"]].to_file(
        ctx.path("exposure_roads"), driver="GPKG")

    buildings_by_class = {HAZARD_CLASS_NAMES[code]: int((out_buildings.hazard_class == code).sum())
                          for code in PRIORITY}
    road_km_by_class = {HAZARD_CLASS_NAMES[code]: round(
        float(out_roads.loc[out_roads.hazard_class == code, "length_m"].sum()) / 1000, 4) for code in PRIORITY}
    bridges_by_class = exposed_bridge_counts(roads, hazard)
    result = {"buildings_by_class": buildings_by_class, "road_km_by_class": road_km_by_class,
              "bridges_by_class": bridges_by_class}
    ctx.log(STAGE, event="complete", **result)
    return result


__all__ = ["exposed_bridge_counts", "exposed_buildings", "exposed_roads", "stage_exposure"]

"""Stage `exposure`: hazard x OSM buildings / roads / bridges. Reported as EXPOSED, never damaged.

Owner: P3. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/03_P3_osm_network.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_exposure(ctx: RunContext) -> dict:
    """Reads: hazard.gpkg, osm_roads, osm_buildings. Writes: exposure_buildings.gpkg, exposure_roads.gpkg.

    Returns: {"buildings_by_class": {class_name: int}, "road_km_by_class": {class_name: float},
              "bridges_by_class": {class_name: int}}
    """
    raise NotImplementedError("P3: implement stage_exposure")

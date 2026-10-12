"""Stage `osm`: pre-event OpenStreetMap snapshot via the ohsome API (v2 with v1 fallback).

Owner: P3. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/03_P3_osm_network.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_osm(ctx: RunContext) -> dict:
    """Writes: osm_roads.gpkg, osm_buildings.gpkg, osm_places.gpkg, osm_health.gpkg (grid CRS).
    MUST call assert_pre_event(ctx.osm_snapshot, ctx.event_datetime) before any request.

    Returns: {"osm_snapshot": str, "osm_api": "v2"|"v1"|"cache", "counts": {layer: int}}
    """
    raise NotImplementedError("P3: implement stage_osm")

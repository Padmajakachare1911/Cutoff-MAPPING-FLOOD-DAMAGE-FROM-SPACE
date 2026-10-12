"""Stage `access`: noded road graph, closure scenarios A/B/C, settlement access status.

Owner: P3. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/03_P3_osm_network.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_access(ctx: RunContext) -> dict:
    """Reads: osm_roads, hazard.gpkg, settlements, targets.
    Writes: settlements_{A,B,C}.gpkg, roads_status_{A,B,C}.gpkg.

    Returns: {"access": [ScenarioResult-compatible dict for A, B, C]} (see cutoff/report/schema.py)
    """
    raise NotImplementedError("P3: implement stage_access")

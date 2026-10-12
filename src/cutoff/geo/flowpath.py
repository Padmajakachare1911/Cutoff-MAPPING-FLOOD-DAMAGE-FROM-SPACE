"""Bonus: trace the flood path downstream from any point with Copernicus DEM; list settlements along it.

Owner: P3. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/03_P3_osm_network.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def trace_flowpath(ctx: RunContext, lon: float, lat: float) -> dict:
    """Writes: flowpath.gpkg. Returns a FlowPath-compatible dict (see cutoff/report/schema.py)."""
    raise NotImplementedError("P3: implement trace_flowpath")

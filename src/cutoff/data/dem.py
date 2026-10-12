"""Stage `terrain`: Copernicus GLO-30 -> dem, slope, HAND, D8 flow directions on the run grid.

Owner: P1. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/01_P1_data_sar.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_terrain(ctx: RunContext) -> dict:
    """Writes: dem.tif, slope.tif, hand.tif, flwdir_d8.tif.

    Returns: {"dem_tiles": [str, ...], "hand_stream_upa_km2": float}
    """
    raise NotImplementedError("P1: implement stage_terrain")

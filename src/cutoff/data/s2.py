"""Stage `s2`: optional Sentinel-2 L2A evidence (MNDWI water + clear-sky mask) near the S1 post date.

Owner: P1. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/01_P1_data_sar.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_s2(ctx: RunContext) -> dict:
    """Writes (only if a usable scene exists): s2_water.tif, s2_clear.tif.

    Returns: {"s2_scenes": [str, ...], "s2_clear_fraction": float | None}
    Must NEVER fail the run: no scene / all cloud -> return {"s2_scenes": [], "s2_clear_fraction": None}
    and ctx.warn(...).
    """
    raise NotImplementedError("P1: implement stage_s2")

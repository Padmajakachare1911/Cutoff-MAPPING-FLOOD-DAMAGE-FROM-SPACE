"""Stage `s1`: search CDSE STAC, pick a same-track pair, acquire calibrated sigma0 on the run grid.

Owner: P1. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/01_P1_data_sar.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_s1(ctx: RunContext) -> dict:
    """Writes: pairs.json, s1_pre_mean.tif, s1_post.tif, lia.tif, shadow_layover.tif.

    Returns (copied into results.inputs by the pipeline):
      {"s1_backend": "sentinelhub"|"snap"|"cached", "rel_orbit": int,
       "orbit_direction": "ascending"|"descending",
       "s1_post": {"id", "datetime", "platform"}, "s1_pre": [{"id", "datetime", "platform"}, ...],
       "post_lag_hours": float}
    Raises cutoff.data.s1_pairs.NoValidPair when no same-track pre/post set exists (never cross-track).
    """
    raise NotImplementedError("P1: implement stage_s1")

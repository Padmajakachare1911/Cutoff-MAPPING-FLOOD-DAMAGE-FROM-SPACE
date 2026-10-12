"""Stage `disturbance`: scene-adaptive same-track backscatter change inside the valley corridor.

Owner: P2. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/02_P2_ml_hazard.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_disturbance(ctx: RunContext) -> dict:
    """Reads: s1_pre_mean.tif, s1_post.tif, hand.tif, shadow_layover.tif. Writes: disturb.tif.

    Returns: {"sigma_stable_db": float, "k_sigma": float, "n_stable_px": int}
    """
    raise NotImplementedError("P2: implement stage_disturbance")

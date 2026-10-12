"""Stage `model`: 7-channel same-track input -> calibrated 3-class probabilities (tiled inference).

Owner: P2. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/02_P2_ml_hazard.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_model(ctx: RunContext) -> dict:
    """Reads: s1_pre_mean.tif, s1_post.tif, slope.tif. Writes: p_model.tif.
    ctx.model_path == "b0" -> rule baseline pseudo-probabilities (works before training exists).

    Returns: {"model_version": str, "flood_threshold": float, "temperature": float}
    """
    raise NotImplementedError("P2: implement stage_model")

"""Stage `gating`: terrain gating + optional S2 evidence -> hazard classes and evidence flags.

Owner: P2. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/02_P2_ml_hazard.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_gating(ctx: RunContext) -> dict:
    """Reads: p_model, disturb, slope, hand, shadow_layover, (s2_water, s2_clear if present).
    Writes: hazard_class.tif, flags.tif.

    Returns: {"stable_steep_fpr": float | None}
    """
    raise NotImplementedError("P2: implement stage_gating")

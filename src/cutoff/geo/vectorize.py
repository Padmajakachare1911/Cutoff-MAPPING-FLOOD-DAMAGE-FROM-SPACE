"""Stage `vectorize`: hazard classes -> polygons and per-class areas (UTM only).

Owner: P2. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/02_P2_ml_hazard.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_vectorize(ctx: RunContext) -> dict:
    """Reads: hazard_class.tif. Writes: hazard.gpkg (layer 'hazard', cols class, area_m2).

    Returns: {"area_km2_by_class": {class_name: km2}, "no_observation_km2": float}
    """
    raise NotImplementedError("P2: implement stage_vectorize")

"""Stage `settlements`: settlements (OSM places + building clusters) and access targets (hospitals, towns).

Owner: P3. Phase-0 STUB: signature and return contract are frozen; replace the body.
See docs/plan/03_P3_osm_network.md for the task list and acceptance tests.
"""
from __future__ import annotations

from cutoff.runctx import RunContext


def stage_settlements(ctx: RunContext) -> dict:
    """Reads: osm_places, osm_buildings, osm_health. Writes: settlements.gpkg, targets.gpkg.

    Returns: {"n_settlements": int, "n_targets": int}
    """
    raise NotImplementedError("P3: implement stage_settlements")

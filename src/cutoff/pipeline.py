"""Pipeline orchestration: AOI + event datetime -> run folder with results.json.

Owner: P4. Phase-0 STUB: the stage ORDER and the stage registry below are frozen
(contract v1.0.0); P4 implements `run`. See docs/plan/04_P4_product.md.

Stage order (each is `fn(ctx) -> dict`, outputs validated with validate_run_dir after each):

  1 s1           P1  cutoff.data.s1_acquire.stage_s1
  2 terrain      P1  cutoff.data.dem.stage_terrain
  3 s2           P1  cutoff.data.s2.stage_s2              (optional; never fails the run)
  4 model        P2  cutoff.ml.infer.stage_model
  5 disturbance  P2  cutoff.geo.change.stage_disturbance
  6 gating       P2  cutoff.geo.gating.stage_gating
  7 vectorize    P2  cutoff.geo.vectorize.stage_vectorize
  8 osm          P3  cutoff.data.osm.stage_osm             (failure -> partial run, hazard still reported)
  9 settlements  P3  cutoff.geo.settlements.stage_settlements
 10 exposure     P3  cutoff.geo.exposure.stage_exposure
 11 access       P3  cutoff.geo.network.stage_access
 12 report       P4  results.json -> sitrep.html / sitrep.pdf
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

STAGES: list[tuple[str, str, tuple[str, ...]]] = [
    # (name, "module:function", contract keys it must produce)
    ("s1", "cutoff.data.s1_acquire:stage_s1", ("s1_pre_mean", "s1_post", "lia", "shadow_layover")),
    ("terrain", "cutoff.data.dem:stage_terrain", ("dem", "slope", "hand", "flwdir")),
    ("s2", "cutoff.data.s2:stage_s2", ("s2_water", "s2_clear")),
    ("model", "cutoff.ml.infer:stage_model", ("p_model",)),
    ("disturbance", "cutoff.geo.change:stage_disturbance", ("disturb",)),
    ("gating", "cutoff.geo.gating:stage_gating", ("hazard_class", "flags")),
    ("vectorize", "cutoff.geo.vectorize:stage_vectorize", ("hazard",)),
    ("osm", "cutoff.data.osm:stage_osm", ("osm_roads", "osm_buildings", "osm_places", "osm_health")),
    ("settlements", "cutoff.geo.settlements:stage_settlements", ("settlements", "targets")),
    ("exposure", "cutoff.geo.exposure:stage_exposure", ("exposure_buildings", "exposure_roads")),
    ("access", "cutoff.geo.network:stage_access",
     ("settlements_A", "settlements_B", "settlements_C", "roads_A", "roads_B", "roads_C")),
]
OPTIONAL_STAGES = ("s2",)            # failure -> warning, run continues
SOFT_FAIL_FROM = "osm"               # failure here or later -> partial results with warning


def run(bbox: tuple[float, float, float, float], event_datetime: datetime, mode: str = "cached",
        model: str = "b0", osm_snapshot: str | None = None, out_root: str | Path = "outputs",
        run_id: str | None = None, stages: list[str] | None = None) -> Path:
    """Run the pipeline and return the run folder. P4 implements (see 04_P4_product.md, task P4.1)."""
    raise NotImplementedError("P4: implement pipeline.run")

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

import copy
import hashlib
import importlib
import json
import math
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
import yaml

from cutoff.contracts import DEFAULT_OSM_SNAPSHOT, RUN_MODES
from cutoff.contracts_check import validate_run_dir
from cutoff.geo.grid import make_grid
from cutoff.report.schema import Results
from cutoff.runctx import RunContext

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


LIMITATIONS = [
    "No early warning: Sentinel-1 revisits a track every 6–12 days; maps show the situation at the post-event pass, "
    "which may be after the peak.",
    "10 m pixels: narrow channels, single roads and small bridges are near or below resolution; closures are "
    "inferred from proximity.",
    "Radar shadow/layover areas cannot be observed from one track and are shown as 'no observation'.",
    "Smooth wet mud can look like water; rough debris is detected only as statistical change, not classified.",
    "Exposure is not damage: no structural assessment is made.",
    "The model score is calibrated on global, mostly lowland floods, not on the Himalaya.",
    "Access results depend on OpenStreetMap completeness; 'unknown' means unmapped, not safe.",
    "Educational prototype, not an operational tool.",
    "Permanent-water scores may include steep radar back-slopes; this class is excluded from hazard exposure.",
]

DEPENDENCIES = {
    "s1": (), "terrain": (), "s2": ("s1",), "model": ("s1", "terrain"),
    "disturbance": ("s1", "terrain"), "gating": ("model", "disturbance", "terrain"),
    "vectorize": ("gating",), "osm": (), "settlements": ("osm",),
    "exposure": ("vectorize", "osm"), "access": ("settlements", "vectorize", "osm"),
}


def parse_event(value: str | datetime) -> tuple[datetime, list[str]]:
    messages = []
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            value += "T23:59:59+00:00"
            messages.append("Bare event date interpreted as 23:59:59 UTC; same-day post-event passes are ignored.")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("event must be an ISO datetime or date")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
        messages.append("Event datetime has no timezone; UTC assumed.")
    return value.astimezone(UTC), messages


def resolve_stage(name, target):
    module, function = target.split(":")
    return getattr(importlib.import_module(module), function)


def render_report(results, root):
    from cutoff.report.sitrep import render
    return render(results, root)


class PeakRSS:
    """Sample process and child RSS while a stage runs (absolute MB, not allocation delta)."""
    def __init__(self):
        self.process = psutil.Process()
        self.peak = 0
        self.stop = threading.Event()

    def sample(self):
        while not self.stop.is_set():
            total = 0
            for process in [self.process, *self.process.children(recursive=True)]:
                try:
                    total += process.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            self.peak = max(self.peak, total)
            self.stop.wait(0.05)

    def __enter__(self):
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.thread.join(timeout=1)


def load_config(path=None):
    if path is None:
        path = Path(__file__).resolve().parent / "resources" / "default.yaml"
        if not path.exists():
            path = Path(__file__).resolve().parents[2] / "configs" / "default.yaml"
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _assemble(ctx):
    s = ctx.summaries
    return Results(
        run_id=ctx.run_id, created_utc=datetime.now(UTC), model_version=s["model"]["model_version"],
        inputs={"aoi_bbox": ctx.aoi_bbox, "grid_epsg": ctx.grid.epsg, "event_datetime": ctx.event_datetime,
                "osm_snapshot": ctx.osm_snapshot, "mode": ctx.mode, **s["s1"],
                **{k: s.get("s2", {}).get(k, default) for k, default in
                   (("s2_scenes", []), ("s2_clear_fraction", None))}},
        hazard={**s["vectorize"], "sigma_stable_db": s["disturbance"].get("sigma_stable_db"),
                "k_sigma": s["disturbance"].get("k_sigma", ctx.cfg["rules"]["k_sigma"]),
                "flood_threshold": s["model"]["flood_threshold"], "temperature": s["model"]["temperature"],
                "stable_steep_fpr": s["gating"].get("stable_steep_fpr")},
        exposure=s.get("exposure"), access=s.get("access", {}).get("access", []),
        flowpath=s.get("flowpath"), warnings=ctx.warnings, timings_s=ctx.timings,
        limitations=list(LIMITATIONS),
    )


def _write_results(ctx):
    results = _assemble(ctx)
    ctx.path("results").write_text(results.model_dump_json(indent=2), encoding="utf-8")
    validate_run_dir(ctx.run_dir, keys=["results"])
    return results


def run(bbox: tuple[float, float, float, float], event_datetime: str | datetime, mode: str = "cached",
        model: str = "b0", osm_snapshot: str | None = None, out_root: str | Path = "outputs",
        run_id: str | None = None, stages: list[str] | None = None, *, config: str | Path | None = None,
        cache_dir: str | Path | None = None, flowpath: tuple[float, float] | None = None) -> Path:
    """Run fresh stages in contract order; never overwrite a previous run.

    A dependency-complete stage subset is permitted. Input-only subsets write
    stage_returns.json, but cannot publish a situation report without hazard outputs.
    """
    event, messages = parse_event(event_datetime)
    if mode not in RUN_MODES:
        raise ValueError(f"mode must be one of {RUN_MODES}")
    if len(bbox) != 4 or not all(math.isfinite(v) for v in bbox):
        raise ValueError("bbox requires four finite W,S,E,N values")
    w, south, east, north = bbox
    if not (-180 <= w < east <= 180 and -80 <= south < north <= 84):
        raise ValueError("bbox must be ordered W,S,E,N inside the UTM latitude range (-80..84)")
    cfg = copy.deepcopy(load_config(config))
    snapshot, _ = parse_event(osm_snapshot or cfg.get("osm", {}).get("snapshot", DEFAULT_OSM_SNAPSHOT))
    if snapshot >= event:
        raise ValueError("OSM snapshot must be strictly before the event")
    snapshot_iso = snapshot.isoformat().replace("+00:00", "Z")
    selected = set(stages if stages is not None else [name for name, _, _ in STAGES])
    if not selected or selected - set(DEPENDENCIES):
        raise ValueError(f"unknown or empty stages: {sorted(selected - set(DEPENDENCIES))}")
    for name in selected:
        missing = set(DEPENDENCIES[name]) - selected
        if missing:
            raise ValueError(f"{name}: missing dependencies {sorted(missing)}")
    if model != "b0" and not Path(model).is_file():
        raise FileNotFoundError(f"model checkpoint missing: {model}; download model-v1 or select b0")
    if flowpath and (len(flowpath) != 2 or not (-180 <= flowpath[0] <= 180 and -80 <= flowpath[1] <= 84)):
        raise ValueError("flowpath must be LON,LAT within the UTM coverage")
    digest = hashlib.sha256(json.dumps(list(bbox)).encode()).hexdigest()[:8]
    run_id = run_id or f"{datetime.now(UTC):%Y%m%dT%H%M%S}_{digest}"
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", run_id)
            or run_id.upper().split('.')[0] in {'CON', 'PRN', 'AUX', 'NUL', *[f'COM{i}' for i in range(1, 10)],
                                              *[f'LPT{i}' for i in range(1, 10)]} or run_id.endswith('.')):
        raise ValueError("run_id must be a safe folder name")
    root = Path(out_root).resolve() / run_id
    root.mkdir(parents=True, exist_ok=False)
    grid = make_grid(bbox)
    grid.to_json(root / "grid.json")
    if cache_dir:
        cfg.setdefault("run", {})["cache_dir"] = str(Path(cache_dir).resolve())
    ctx = RunContext(root, run_id, bbox, event, snapshot_iso, mode, cfg, grid, model_path=model)
    for message in messages:
        ctx.warn("inputs", message)
    ctx.log("pipeline", event="start", bbox=bbox, event_datetime=event, osm_snapshot=snapshot_iso,
            mode=mode, model=model, config_sha256=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest())
    if model != "b0":
        ctx.log("pipeline", model_sha256=hashlib.sha256(Path(model).read_bytes()).hexdigest())
    base_cache = cfg.get("run", {}).get("cache_dir", "cache")
    osm_identity = {"snapshot": snapshot_iso, "access": cfg.get("access", {}), "osm": cfg.get("osm", {})}
    osm_hash = hashlib.sha256(json.dumps(osm_identity, sort_keys=True).encode()).hexdigest()[:16]
    current = "pipeline"
    try:
        for name, target, keys in STAGES:
            if name not in selected:
                continue
            current = name
            start = time.perf_counter()
            ctx.log(name, event="start")
            # P3's legacy cache lacks snapshot provenance. Namespace only this stage.
            cfg.setdefault("run", {})["cache_dir"] = (
                str(Path(base_cache) / "dated_osm" / osm_hash) if name == "osm" else str(base_cache))
            failed = False
            with PeakRSS() as rss:
                try:
                    summary = resolve_stage(name, target)(ctx) or {}
                    if not isinstance(summary, dict):
                        raise TypeError(f"{name} must return a dictionary")
                    present = [key for key in keys if ctx.has(key)] if name in OPTIONAL_STAGES else list(keys)
                    if name == "s2" and present and len(present) != len(keys):
                        raise ValueError("S2 must produce both optional rasters or neither")
                    validate_run_dir(root, keys=present)
                    ctx.summaries[name] = summary
                except Exception as exc:
                    failed = True
                    # Failed stage outputs never enter consumers or UI as valid data.
                    for key in keys:
                        ctx.path(key).unlink(missing_ok=True)
                    if name in OPTIONAL_STAGES:
                        ctx.warn(name, f"Optional {name} skipped: {exc}")
                        ctx.summaries[name] = {}
                    elif [n for n, _, _ in STAGES].index(name) >= [n for n, _, _ in STAGES].index(SOFT_FAIL_FROM):
                        ctx.warn(name, f"Partial run: {name} failed; dependent stages skipped: {exc}")
                    else:
                        raise
                finally:
                    ctx.timings[name] = round(time.perf_counter() - start, 4)
            ctx.log(name, event="failed" if failed else "complete", elapsed_s=ctx.timings[name],
                    peak_rss_mb=round(rss.peak / 1024**2, 2), summary=ctx.summaries.get(name))
            if failed and name not in OPTIONAL_STAGES:
                break
        cfg["run"]["cache_dir"] = str(base_cache)
        if flowpath:
            if mode == "cached":
                ctx.warn("flowpath", "Flow path skipped in cached mode: current tracing implementation needs network.")
            else:
                try:
                    from cutoff.geo.flowpath import trace_flowpath
                    ctx.summaries["flowpath"] = trace_flowpath(ctx, *flowpath)
                    validate_run_dir(root, keys=["flowpath"])
                except Exception as exc:
                    ctx.path("flowpath").unlink(missing_ok=True)
                    ctx.warn("flowpath", f"Optional flow path skipped: {exc}")
        (root / "stage_returns.json").write_text(json.dumps(ctx.summaries, indent=2, default=str), encoding="utf-8")
        if "vectorize" not in ctx.summaries:
            ctx.log("pipeline", event="staged", message="Input-only subset; no results.json until hazard stages run.")
            return root
        if "exposure" not in ctx.summaries or "access" not in ctx.summaries:
            if not any("Partial run" in warning for warning in ctx.warnings):
                ctx.warn("pipeline", "Partial run: exposure/access stages were not selected.")
        results = _write_results(ctx)
        current = "report"
        start = time.perf_counter()
        try:
            render_report(results, root)
        except (ImportError, OSError, RuntimeError) as exc:
            ctx.warn("report", f"Situation report unavailable: {exc}; results.json is ready.")
        ctx.timings["report"] = round(time.perf_counter() - start, 4)
        _write_results(ctx)
        ctx.log("pipeline", event="complete", partial=any("Partial run" in warning for warning in ctx.warnings))
        return root
    except Exception as exc:
        ctx.path("results").unlink(missing_ok=True)
        (root / "error.json").write_text(json.dumps({"run_id": run_id, "stage": current,
            "error_type": type(exc).__name__, "message": str(exc), "warnings": ctx.warnings,
            "timings_s": ctx.timings}, indent=2), encoding="utf-8")
        ctx.log(current, event="error", error_type=type(exc).__name__, message=str(exc))
        raise

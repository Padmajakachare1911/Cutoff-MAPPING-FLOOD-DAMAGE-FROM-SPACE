"""Fill the input cache for a demo AOI: run stages s1, terrain and s2 (fast mode by default).  Owner: P1.

    python scripts/cache_aoi.py --name trishuli_north --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z

Writes the stage outputs to <cache_dir>/<name>/ (grid.json, pairs.json, s1_*, lia, shadow_layover, dem, slope,
hand, flwdir_d8, s2_* + run.log + stage_returns.json) and fills the reusable caches the stages keep
(<cache_dir>/s1/<scene>/<grid_hash>.tif, <cache_dir>/s1/stac/, <cache_dir>/dem/, <cache_dir>/s2/), so a later
`cutoff run ... --mode cached` on the same bbox needs no network. Each stage's outputs are validated with
validate_run_dir. s2 is optional: its failure is a warning, never an error.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cutoff.contracts import DEFAULT_OSM_SNAPSHOT  # noqa: E402
from cutoff.contracts_check import validate_run_dir  # noqa: E402
from cutoff.geo.grid import make_grid  # noqa: E402
from cutoff.runctx import RunContext  # noqa: E402

STAGES = {
    "s1": ("cutoff.data.s1_acquire", "stage_s1", ["s1_pre_mean", "s1_post", "lia", "shadow_layover"]),
    "terrain": ("cutoff.data.dem", "stage_terrain", ["dem", "slope", "hand", "flwdir"]),
    "s2": ("cutoff.data.s2", "stage_s2", ["s2_water", "s2_clear"]),
}
OPTIONAL = {"s2"}


def parse_event(s: str) -> datetime:
    if "T" not in s:  # bare date = end of that day (05_contracts.md section 6)
        return datetime.fromisoformat(s).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv=None) -> int:
    import importlib

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", required=True)
    ap.add_argument("--bbox", required=True, help="W,S,E,N degrees")
    ap.add_argument("--event", required=True, help="event datetime UTC, e.g. 2026-08-26T02:52:00Z")
    ap.add_argument("--mode", default="fast", choices=["fast", "full", "cached"])
    ap.add_argument("--stages", default="s1,terrain,s2")
    ap.add_argument("--allow-cross-track", action="store_true", help="experiment E5 only")
    ap.add_argument("--config", default=str(ROOT / "configs" / "default.yaml"))
    ap.add_argument("--out", default=None, help="run folder (default <cache_dir>/<name>)")
    a = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))
    if a.allow_cross_track:
        cfg["s1"]["allow_cross_track"] = True
    bbox = tuple(float(v) for v in a.bbox.split(","))
    run = Path(a.out) if a.out else Path(cfg["run"]["cache_dir"]) / a.name
    run.mkdir(parents=True, exist_ok=True)
    grid = make_grid(bbox, res=float(cfg["run"].get("pixel_m", 10)))
    grid.to_json(run / "grid.json")
    ctx = RunContext(run_dir=run, run_id=a.name, aoi_bbox=bbox, event_datetime=parse_event(a.event),
                     osm_snapshot=cfg.get("osm", {}).get("snapshot", DEFAULT_OSM_SNAPSHOT), mode=a.mode,
                     cfg=cfg, grid=grid)
    returns, status = {}, 0
    for name in a.stages.split(","):
        mod, fn, keys = STAGES[name]
        t0 = time.time()
        try:
            returns[name] = getattr(importlib.import_module(mod), fn)(ctx)
            validate_run_dir(run, keys=keys)
            ctx.timings[name] = round(time.time() - t0, 1)
            print(f"[{name}] OK in {ctx.timings[name]} s: {json.dumps(returns[name], default=str)}")
        except Exception as e:  # noqa: BLE001 - report every stage, s2 never fails the run
            if name in OPTIONAL:
                ctx.warn(name, f"{name} failed: {type(e).__name__}: {e}")
                print(f"[{name}] WARNING (optional stage): {type(e).__name__}: {e}")
                continue
            print(f"[{name}] FAILED: {type(e).__name__}: {e}")
            ctx.log(name, level="error", message=f"{type(e).__name__}: {e}")
            status = 1  # keep going: the other stages are independent inputs
    (run / "stage_returns.json").write_text(json.dumps({"name": a.name, "bbox": bbox, "event": a.event,
                                                        "mode": a.mode, "returns": returns, "timings": ctx.timings,
                                                        "warnings": ctx.warnings}, indent=1, default=str),
                                            encoding="utf-8")
    for w in ctx.warnings:
        print("warning:", w)
    print("run folder:", run.resolve())
    return status


if __name__ == "__main__":
    raise SystemExit(main())

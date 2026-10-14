"""E7: collect real run logs or launch the reproducible nominal-size benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import psutil
from pyproj import Transformer

from cutoff.geo.grid import utm_epsg

ROOT = Path(__file__).resolve().parents[1]


def collect(root):
    root = Path(root)
    logs = [
        json.loads(line)
        for line in (root / "run.log").read_text(encoding="utf-8").splitlines()
    ]
    starts = [
        row["t"]
        for row in logs
        if row.get("stage") == "pipeline" and row.get("event") == "start"
    ]
    ends = [
        row["t"]
        for row in logs
        if row.get("stage") == "pipeline" and row.get("event") in ("complete", "error")
    ]
    stages = [row for row in logs if "elapsed_s" in row]
    result = {
        "run": root.name,
        "pipeline_wall_s": ends[-1] - starts[0] if starts and ends else None,
        "stage_s": {row["stage"]: row["elapsed_s"] for row in stages},
        "peak_rss_mb": max((row.get("peak_rss_mb", 0) for row in stages), default=None),
        "partial": any(row.get("partial", False) for row in logs),
    }
    path = root / "results.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        result.update(
            mode=data["inputs"]["mode"],
            model=data["model_version"],
            warnings=data["warnings"],
        )
    elif (root / "error.json").exists():
        result["error"] = json.loads((root / "error.json").read_text(encoding="utf-8"))[
            "message"
        ]
    return result


def square_bbox(lon, lat, size_km):
    epsg = utm_epsg(lon, lat)
    x, y = Transformer.from_crs(4326, epsg, always_xy=True).transform(lon, lat)
    half = size_km * 500
    inverse = Transformer.from_crs(epsg, 4326, always_xy=True)
    xs, ys = inverse.transform(
        [x - half, x - half, x + half, x + half],
        [y - half, y + half, y - half, y + half],
    )
    return min(xs), min(ys), max(xs), max(ys)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="*", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--center", default="85.35,28.195")
    parser.add_argument("--event", default="2026-08-26T02:52:00Z")
    parser.add_argument("--osm-snapshot", default="2026-07-27T00:00:00Z")
    parser.add_argument(
        "--models", nargs="+", default=["b0", "models/cutoff_unet_v1.pt"]
    )
    parser.add_argument("--out", type=Path, default=ROOT / "docs/results/raw/E7.json")
    args = parser.parse_args()
    rows = [collect(root) for root in args.runs or []]
    if args.benchmark:
        lon, lat = map(float, args.center.split(","))
        for size in (10, 20, 40):
            for index, model in enumerate(args.models):
                run_id = f"e7_{size}km_m{index}_{time.time_ns()}"
                root = ROOT / "outputs" / run_id
                command = [
                    sys.executable,
                    "-m",
                    "cutoff.cli",
                    "run",
                    "--bbox",
                    ",".join(map(str, square_bbox(lon, lat, size))),
                    "--event",
                    args.event,
                    "--osm-snapshot",
                    args.osm_snapshot,
                    "--mode",
                    "fast",
                    "--model",
                    model,
                    "--out",
                    str(ROOT / "outputs"),
                    "--run-id",
                    run_id,
                ]
                started = time.perf_counter()
                completed = subprocess.run(
                    command, cwd=ROOT, capture_output=True, text=True
                )
                row = (
                    collect(root)
                    if (root / "run.log").exists()
                    else {"run": run_id, "error": completed.stderr[-1000:]}
                )
                row.update(
                    nominal_size_km=size,
                    cli_wall_s=time.perf_counter() - started,
                    exit_code=completed.returncode,
                )
                rows.append(row)
    if not rows:
        parser.error("choose --runs or --benchmark")
    record = {
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "logical_cpus": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
        },
        "notes": "RSS is process plus children; excludes GPU VRAM. Label cache state separately.",
        "runs": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()

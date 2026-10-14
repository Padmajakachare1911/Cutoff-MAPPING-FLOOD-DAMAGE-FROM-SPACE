"""Local web server for the Cutoff dashboard.

The server deliberately uses only Python's standard HTTP stack.  It serves the
static dashboard, exposes validated run data, renders the existing Folium map,
and can launch pipeline runs in the background.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import mimetypes
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from cutoff.cli import load_dotenv
from cutoff.contracts import DEFAULT_OSM_SNAPSHOT, DISCLAIMER
from cutoff.pipeline import parse_event
from cutoff.report.schema import Results

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUTPUT = Path(os.environ.get("CUTOFF_OUTPUT_DIR", ROOT / "outputs")).resolve()
DOWNLOADS = {
    "sitrep.pdf",
    "hazard.gpkg",
    "hazard_class.tif",
    "results.json",
    "flowpath.gpkg",
    "settlements_A.gpkg",
    "settlements_B.gpkg",
    "settlements_C.gpkg",
}
DISPLAY_LAYERS = {
    "hazard": ("hazard_class.tif", "hazard", 1),
    "no_observation": ("hazard_class.tif", "no_obs", 1),
    "score": ("p_model.tif", "score", 3),
    "pre": ("s1_pre_mean.tif", "gray", 1),
    "post": ("s1_post.tif", "gray", 1),
    "s2": ("s2_water.tif", "s2", 1),
}
PROCESSES: dict[str, subprocess.Popen] = {}
PROCESS_LOCK = threading.Lock()


@lru_cache(maxsize=64)
def display_png(path: Path, kind: str, band: int) -> bytes:
    from map_layers import raster_overlay
    from PIL import Image
    image, _ = raster_overlay(path, kind, band=band)
    stream = io.BytesIO()
    Image.fromarray(image).save(stream, format="PNG")
    return stream.getvalue()


def display_bounds(path: Path) -> list:
    import rasterio
    from rasterio.warp import transform_bounds
    with rasterio.open(path) as source:
        projected = transform_bounds(source.crs, "EPSG:3857", *source.bounds)
        west, south, east, north = transform_bounds("EPSG:3857", "EPSG:4326", *projected)
    return [[south, west], [north, east]]


def default_cache() -> Path:
    return Path(os.environ.get("CUTOFF_CACHE_DIR", ROOT / "cache")).expanduser().resolve()


def full_mode_unavailable() -> str | None:
    import shutil

    from cutoff.data.snap import SnapNotFound, find_gpt
    try:
        gpt = find_gpt()
        if not Path(gpt).is_file() and not shutil.which(gpt):
            raise SnapNotFound("SNAP_GPT does not point to an installed executable")
    except SnapNotFound:
        return "Full mode requires ESA SNAP installed and SNAP_GPT configured. Choose Fast for Sentinel Hub processing."
    if not all(os.environ.get(key, "").strip() for key in ("CDSE_USERNAME", "CDSE_PASSWORD")):
        return "Full mode requires CDSE_USERNAME and CDSE_PASSWORD in the private .env. Choose Fast or configure them."
    return None


def run_state(root: Path) -> str:
    with PROCESS_LOCK:
        process = PROCESSES.get(root.name)
    if process and process.poll() is None:
        return "running"
    if (root / "results.json").is_file():
        r = Results.model_validate_json((root / "results.json").read_text(encoding="utf-8"))
        return "partial" if r.is_partial else "complete"
    if (root / "error.json").is_file() or (process and process.poll() is not None):
        return "failed"
    return "incomplete"


def run_root(run_id: str) -> Path:
    """Resolve a run name inside OUTPUT, rejecting traversal and nested paths."""
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid run id")
    root = (OUTPUT / run_id).resolve()
    if root.parent != OUTPUT:
        raise ValueError("Invalid run id")
    return root


def list_runs() -> list[dict]:
    if not OUTPUT.is_dir():
        return []
    items = []
    for path in OUTPUT.iterdir():
        if not path.is_dir():
            continue
        state = run_state(path)
        if state == "incomplete":
            continue
        items.append({"id": path.name, "state": state, "modified": path.stat().st_mtime})
    known = {item["id"] for item in items}
    with PROCESS_LOCK:
        for run_id, process in PROCESSES.items():
            if run_id not in known and process.poll() is None:
                items.append({"id": run_id, "state": "running", "modified": time.time()})
    return sorted(items, key=lambda item: item["modified"], reverse=True)


def read_run(run_id: str) -> dict:
    root = run_root(run_id)
    result = root / "results.json"
    error = root / "error.json"
    state = run_state(root)
    if state in {"complete", "partial"}:
        r = Results.model_validate_json(result.read_text(encoding="utf-8"))
        frozen = ROOT / "docs/results/frozen_runs.txt"
        evaluation = {}
        if frozen.is_file() and run_id in frozen.read_text(encoding="utf-8").splitlines():
            for name in ("P2_kuro_results.md", "E4.md", "E6.md"):
                path = ROOT / "docs/results" / name
                if path.is_file():
                    evaluation[name] = path.read_text(encoding="utf-8")
        return {"state": state, "results": r.model_dump(mode="json"),
                "downloads": sorted(name for name in DOWNLOADS if (root / name).is_file()
                                    and (not name.startswith("settlements_")
                                         or any(name == f"settlements_{s.scenario}.gpkg" for s in r.access))
                                    and (name != "flowpath.gpkg" or r.flowpath is not None)),
                "evaluation": evaluation}
    if error.is_file():
        return {"state": "failed", "error": json.loads(error.read_text(encoding="utf-8"))}
    log = root / "run.log"
    lines = log.read_text(encoding="utf-8").splitlines()[-20:] if log.is_file() else []
    if state == "failed":
        console = OUTPUT / f"{run_id}.console.log"
        return {"state": "failed", "error": {"message": console.read_text(encoding="utf-8")[-2500:]
                if console.is_file() else "The process stopped before producing results."}, "log": lines}
    return {"state": state, "log": lines}


def validate_launch(payload: dict) -> list[str]:
    from cutoff.cli import coordinates

    bbox = str(payload.get("bbox", ""))
    west, south, east, north = coordinates(bbox)
    if not all(math.isfinite(v) for v in (west, south, east, north)) or not (
            -180 <= west < east <= 180 and -80 <= south < north <= 84):
        raise ValueError("Analysis bounds must be ordered W,S,E,N within the supported latitude range")
    event, _ = parse_event(str(payload.get("event", "")))
    snapshot, _ = parse_event(str(payload.get("snapshot", DEFAULT_OSM_SNAPSHOT)))
    if snapshot >= event:
        raise ValueError("OSM snapshot must be strictly before the event")
    mode = str(payload.get("mode", "fast"))
    if mode not in {"cached", "fast", "full"}:
        raise ValueError("Mode must be cached, fast, or full")
    if mode == "full" and (reason := full_mode_unavailable()):
        raise ValueError(reason)
    model = str(payload.get("model") or ROOT / "models" / "cutoff_unet_v1.pt")
    if model != "b0" and not Path(model).expanduser().is_file():
        raise ValueError("Download model-v1 or choose b0")
    cache = str(Path(payload.get("cache") or default_cache()).expanduser().resolve())
    legacy = (ROOT / "cache").resolve()
    if Path(cache) == legacy and not (legacy / "s1/stac").is_dir() and (default_cache() / "s1/stac").is_dir():
        cache = str(default_cache())  # an already-open browser may submit the previous empty default
    return [bbox, str(payload["event"]), mode, model, str(payload.get("snapshot", DEFAULT_OSM_SNAPSHOT)), cache]


def launch_run(payload: dict) -> str:
    bbox, event, mode, model, snapshot, cache = validate_launch(payload)
    source = str(payload.get("flowpath", "")).strip()
    if source:
        from cutoff.cli import coordinates
        lon, lat = coordinates(source, 2)
        if not (-180 <= lon <= 180 and -80 <= lat <= 84):
            raise ValueError("Flow source must be a valid longitude,latitude")
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "cutoff.cli", "run", "--bbox", bbox, "--event", event,
        "--mode", mode, "--model", model, "--osm-snapshot", snapshot, "--out", str(OUTPUT),
        "--run-id", run_id, "--cache-dir", cache,
    ]
    console = OUTPUT / f"{run_id}.console.log"
    stream = console.open("w", encoding="utf-8")
    if source:
        command.extend(["--flowpath", source])
    with PROCESS_LOCK:
        if any(p.poll() is None for p in PROCESSES.values()):
            stream.close()
            raise ValueError("An analysis is already running. Wait for it to finish before starting another.")
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        finally:
            stream.close()
        PROCESSES[run_id] = process
    return run_id


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CutoffLocal/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

    def send_bytes(self, data: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK, *, download: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_bytes(json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_error_json(self, message: str, status: HTTPStatus) -> None:
        self.send_json({"error": message}, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                return self.serve_static("index.html")
            if parsed.path.startswith("/static/"):
                return self.serve_static(unquote(parsed.path.removeprefix("/static/")))
            if parsed.path == "/api/config":
                return self.send_json({
                    "disclaimer": DISCLAIMER,
                    "default_snapshot": DEFAULT_OSM_SNAPSHOT,
                    "default_cache": str(default_cache()),
                    "default_model": str(ROOT / "models" / "cutoff_unet_v1.pt"),
                    "full_mode_unavailable": full_mode_unavailable(),
                })
            if parsed.path == "/api/runs":
                return self.send_json(list_runs())
            if parsed.path.startswith("/api/runs/"):
                return self.send_json(read_run(unquote(parsed.path.removeprefix("/api/runs/"))))
            if parsed.path.startswith("/api/map-data/"):
                run_id = unquote(parsed.path.removeprefix("/api/map-data/"))
                scenario = parse_qs(parsed.query).get("scenario", ["A"])[0]
                if scenario not in {"A", "B", "C"}:
                    raise ValueError("Invalid scenario")
                root = run_root(run_id)
                results = Results.model_validate_json((root / "results.json").read_text(encoding="utf-8"))
                from map_layers import vector_data

                vectors = {}
                for key, filename in {
                    "roads": "osm_roads.gpkg",
                    "exposed_buildings": "exposure_buildings.gpkg",
                    "exposed_roads": "exposure_roads.gpkg",
                    "closed_roads": f"roads_status_{scenario}.gpkg",
                    "settlements": f"settlements_{scenario}.gpkg",
                    "flowpath": "flowpath.gpkg",
                    "hazard_polygons": "hazard.gpkg",
                }.items():
                    if key in {"exposed_buildings", "exposed_roads"} and results.exposure is None:
                        continue
                    if key in {"closed_roads", "settlements"} and not any(s.scenario == scenario for s in results.access):
                        continue
                    if key == "flowpath" and results.flowpath is None:
                        continue
                    path = root / filename
                    if path.is_file():
                        data = vector_data(path)
                        if key == "closed_roads":
                            data["features"] = [f for f in data["features"] if f["properties"].get("closed")]
                        vectors[key] = data
                layers = {}
                for name, (filename, kind, band) in DISPLAY_LAYERS.items():
                    if (root / filename).is_file():
                        bounds = display_bounds(root / filename)
                        layers[name] = {"url": f"/api/layers/{run_id}/{name}.png", "bounds": bounds}
                return self.send_json({
                    "run_id": run_id,
                    "scenario": scenario,
                    "bounds": list(results.inputs.aoi_bbox),
                    "hazard_url": f"/api/layers/{run_id}/hazard.png",
                    "vectors": vectors,
                    "layers": layers,
                    "terrain_url": f"/api/terrain/{run_id}/{{z}}/{{x}}/{{y}}.png" if (root / "dem.tif").is_file() else None,
                })
            if parsed.path.startswith("/api/terrain/"):
                parts = unquote(parsed.path.removeprefix("/api/terrain/")).split("/")
                if len(parts) != 4 or not parts[3].endswith(".png"):
                    raise ValueError("Invalid terrain tile")
                from terrain_tiles import terrain_png
                data = terrain_png(run_root(parts[0]) / "dem.tif", int(parts[1]), int(parts[2]), int(parts[3][:-4]))
                return self.send_bytes(data, "image/png")
            if parsed.path.startswith("/api/layers/"):
                parts = unquote(parsed.path.removeprefix("/api/layers/")).split("/", 1)
                if len(parts) != 2 or parts[1].removesuffix(".png") not in DISPLAY_LAYERS:
                    raise ValueError("Invalid map layer")
                filename, kind, band = DISPLAY_LAYERS[parts[1].removesuffix(".png")]
                return self.send_bytes(display_png(run_root(parts[0]) / filename, kind, band), "image/png")
            if parsed.path.startswith("/api/files/"):
                parts = unquote(parsed.path.removeprefix("/api/files/")).split("/", 1)
                if len(parts) != 2 or parts[1] not in DOWNLOADS:
                    raise ValueError("Invalid download")
                path = run_root(parts[0]) / parts[1]
                if not path.is_file():
                    return self.send_error_json("File not found", HTTPStatus.NOT_FOUND)
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                return self.send_bytes(path.read_bytes(), content_type, download=path.name)
            self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
        except ConnectionError:
            return  # switching runs cancels in-flight image/tile requests
        except FileNotFoundError:
            self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/runs":
            return self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 64_000:
                raise ValueError("Request is too large")
            payload = json.loads(self.rfile.read(length) or b"{}")
            run_id = launch_run(payload)
            self.send_json({"id": run_id, "state": "running"}, HTTPStatus.ACCEPTED)
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_error_json(str(exc), HTTPStatus.BAD_REQUEST)

    def serve_static(self, name: str) -> None:
        path = (STATIC / name).resolve()
        if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
            return self.send_error_json("Not found", HTTPStatus.NOT_FOUND)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(path.read_bytes(), f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), DashboardHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Cutoff dashboard locally")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"Cutoff dashboard: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

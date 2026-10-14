"""Local web server for the Cutoff dashboard.

The server deliberately uses only Python's standard HTTP stack.  It serves the
static dashboard, exposes validated run data, renders the existing Folium map,
and can launch pipeline runs in the background.
"""
from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import subprocess
import sys
import threading
import uuid
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from cutoff.contracts import DEFAULT_OSM_SNAPSHOT, DISCLAIMER
from cutoff.pipeline import parse_event
from cutoff.report.schema import Results

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUTPUT = Path(os.environ.get("CUTOFF_OUTPUT_DIR", ROOT / "outputs")).resolve()
DOWNLOADS = {
    "sitrep.pdf",
    "hazard.gpkg",
    "hazard_class.tif",
    "results.json",
    "settlements_A.gpkg",
    "settlements_B.gpkg",
    "settlements_C.gpkg",
}
PROCESSES: dict[str, subprocess.Popen] = {}
PROCESS_LOCK = threading.Lock()


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
        result, error = path / "results.json", path / "error.json"
        with PROCESS_LOCK:
            process = PROCESSES.get(path.name)
        state = "running" if process and process.poll() is None else "complete" if result.is_file() else "failed" if error.is_file() else "incomplete"
        if state == "incomplete":
            continue
        items.append({"id": path.name, "state": state, "modified": path.stat().st_mtime})
    return sorted(items, key=lambda item: item["modified"], reverse=True)


def read_run(run_id: str) -> dict:
    root = run_root(run_id)
    result = root / "results.json"
    error = root / "error.json"
    if result.is_file():
        return {"state": "complete", "results": Results.model_validate_json(result.read_text(encoding="utf-8")).model_dump(mode="json")}
    if error.is_file():
        return {"state": "failed", "error": json.loads(error.read_text(encoding="utf-8"))}
    with PROCESS_LOCK:
        process = PROCESSES.get(run_id)
    log = root / "run.log"
    lines = log.read_text(encoding="utf-8").splitlines()[-20:] if log.is_file() else []
    return {"state": "running" if process and process.poll() is None else "incomplete", "log": lines}


def validate_launch(payload: dict) -> list[str]:
    from cutoff.cli import coordinates

    bbox = str(payload.get("bbox", ""))
    coordinates(bbox)
    event, _ = parse_event(str(payload.get("event", "")))
    snapshot, _ = parse_event(str(payload.get("snapshot", DEFAULT_OSM_SNAPSHOT)))
    if snapshot >= event:
        raise ValueError("OSM snapshot must be strictly before the event")
    mode = str(payload.get("mode", "cached"))
    if mode not in {"cached", "fast", "full"}:
        raise ValueError("Mode must be cached, fast, or full")
    model = str(payload.get("model") or ROOT / "models" / "cutoff_unet_v1.pt")
    if model != "b0" and not Path(model).expanduser().is_file():
        raise ValueError("Download model-v1 or choose b0")
    cache = str(payload.get("cache", ROOT / "cache"))
    return [bbox, str(payload["event"]), mode, model, str(payload.get("snapshot", DEFAULT_OSM_SNAPSHOT)), cache]


def launch_run(payload: dict) -> str:
    bbox, event, mode, model, snapshot, cache = validate_launch(payload)
    run_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S}_{uuid.uuid4().hex[:8]}"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "cutoff.cli", "run", "--bbox", bbox, "--event", event,
        "--mode", mode, "--model", model, "--osm-snapshot", snapshot, "--out", str(OUTPUT),
        "--run-id", run_id, "--cache-dir", cache,
    ]
    console = OUTPUT / f"{run_id}.console.log"
    stream = console.open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    with PROCESS_LOCK:
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
                    "default_cache": str(ROOT / "cache"),
                    "default_model": str(ROOT / "models" / "cutoff_unet_v1.pt"),
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
                from map_layers import derived_flowline, vector_data

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
                    path = root / filename
                    if path.is_file():
                        data = vector_data(path)
                        if key == "closed_roads":
                            data["features"] = [f for f in data["features"] if f["properties"].get("closed")]
                        vectors[key] = data
                if "flowpath" not in vectors:
                    fallback = derived_flowline(root)
                    if fallback:
                        vectors["derived_flow"] = fallback
                return self.send_json({
                    "run_id": run_id,
                    "scenario": scenario,
                    "bounds": list(results.inputs.aoi_bbox),
                    "hazard_url": f"/api/layers/{run_id}/hazard.png",
                    "vectors": vectors,
                })
            if parsed.path.startswith("/api/layers/"):
                parts = unquote(parsed.path.removeprefix("/api/layers/")).split("/", 1)
                if len(parts) != 2 or parts[1] != "hazard.png":
                    raise ValueError("Invalid map layer")
                from map_layers import raster_overlay
                from PIL import Image

                image, _ = raster_overlay(run_root(parts[0]) / "hazard_class.tif", "hazard")
                stream = io.BytesIO()
                Image.fromarray(image, mode="RGBA").save(stream, format="PNG")
                return self.send_bytes(stream.getvalue(), "image/png")
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
        if path.parent != STATIC.resolve() or not path.is_file():
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

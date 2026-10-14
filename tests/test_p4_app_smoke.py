import importlib.util
import json
import threading
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from cutoff.mock import make_mock_run

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "app" / "server.py"


def load_server(output):
    spec = importlib.util.spec_from_file_location("cutoff_dashboard_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = output.resolve()
    return module


def get_json(base, path):
    with urlopen(base + path) as response:
        return json.load(response)


def test_local_dashboard_serves_mock_scenarios_and_downloads(tmp_path):
    make_mock_run(tmp_path / "demo_mock")
    module = load_server(tmp_path)
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/") as response:
            page = response.read().decode()
        assert "Cutoff" in page and "RUN ANALYSIS" in page
        assert get_json(base, "/api/runs")[0]["id"] == "demo_mock"
        payload = get_json(base, "/api/runs/demo_mock")
        assert payload["results"]["access"][0]["counts"]["cut_off"] == 2
        assert payload["results"]["access"][1]["counts"]["cut_off"] == 1
        map_data = get_json(base, "/api/map-data/demo_mock?scenario=B")
        assert map_data["scenario"] == "B"
        assert map_data["vectors"]["settlements"]["features"]
        assert map_data["vectors"]["hazard_polygons"]["features"]
        assert map_data["vectors"]["derived_flow"]["features"][0]["properties"]["direction"] == "downhill"
        with urlopen(base + "/api/layers/demo_mock/hazard.png") as response:
            assert response.headers["Content-Type"] == "image/png"
            assert response.read(8) == b"\x89PNG\r\n\x1a\n"
        with urlopen(base + "/api/files/demo_mock/results.json") as response:
            assert response.headers["Content-Disposition"].startswith("attachment")
    finally:
        server.shutdown()
        server.server_close()


def test_error_run_is_returned(tmp_path):
    root = tmp_path / "bad"
    root.mkdir()
    (root / "error.json").write_text(json.dumps({"error_type": "NoValidPair", "message": "Tracks seen: 85"}))
    module = load_server(tmp_path)
    assert module.read_run("bad")["error"]["message"] == "Tracks seen: 85"


def test_raster_overlay_uses_mercator_and_masks_nodata(tmp_path):
    root = make_mock_run(tmp_path / "mock")
    path = ROOT / "app" / "map_layers.py"
    spec = importlib.util.spec_from_file_location("map_layers", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image, bounds = module.raster_overlay(root / "hazard_class.tif", "hazard")
    assert image.shape[-1] == 4 and image.dtype == np.uint8
    assert bounds[0][0] < bounds[1][0] and bounds[0][1] < bounds[1][1]
    assert np.any(image[..., 3] == 0)

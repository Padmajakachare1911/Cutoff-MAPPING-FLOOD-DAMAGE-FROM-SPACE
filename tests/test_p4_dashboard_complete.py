import importlib.util
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image

from cutoff.mock import make_mock_run
from cutoff.report.schema import Results

ROOT = Path(__file__).resolve().parents[1]


def server(output):
    spec = importlib.util.spec_from_file_location("dashboard_complete", ROOT / "app/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUTPUT = output
    return module


def test_configured_cache_is_used_by_launch(tmp_path, monkeypatch):
    module = server(tmp_path)
    monkeypatch.setenv("CUTOFF_CACHE_DIR", str(tmp_path / "prepared"))
    args = module.validate_launch({"bbox": "85.28,28.1,85.42,28.29", "event": "2026-08-26T02:52:00Z", "model": "b0"})
    assert args[2] == "fast" and args[-1] == str((tmp_path / "prepared").resolve())


def test_real_partial_state_and_totals_are_reported(tmp_path):
    root = make_mock_run(tmp_path / "partial")
    data = json.loads((root / "results.json").read_text(encoding="utf-8"))
    data["hazard"]["area_km2_by_class"]["permanent_water"] = 900
    data["exposure"] = None
    data["access"] = []
    (root / "results.json").write_text(json.dumps(data), encoding="utf-8")
    module = server(tmp_path)
    payload = module.read_run("partial")
    assert payload["state"] == "partial" and module.list_runs()[0]["state"] == "partial"
    assert payload["results"]["is_partial"] is True
    expected = sum(data["hazard"]["area_km2_by_class"][k] for k in
                   ("flood_high", "flood_possible", "rule_decrease", "rule_increase"))
    assert payload["results"]["hazard"]["total_hazard_km2"] == round(expected, 4)
    assert payload["evaluation"] == {}
    assert not any(name.startswith("settlements_") for name in payload["downloads"])


def test_evaluation_is_exposed_only_for_listed_frozen_run(tmp_path, monkeypatch):
    make_mock_run(tmp_path / "mock")
    module = server(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    results = tmp_path / "docs/results"
    results.mkdir(parents=True)
    (results / "E4.md").write_text("Measured frozen evidence", encoding="utf-8")
    assert module.read_run("mock")["evaluation"] == {}
    (results / "frozen_runs.txt").write_text("mock\n", encoding="utf-8")
    assert module.read_run("mock")["evaluation"] == {"E4.md": "Measured frozen evidence"}


def test_copernicus_dem_encodes_local_terrain_without_external_tiles(tmp_path):
    root = make_mock_run(tmp_path / "mock")
    spec = importlib.util.spec_from_file_location("terrain_tiles", ROOT / "app/terrain_tiles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # A tile covering the mock AOI, at a useful terrain zoom.
    import math
    z = 12
    lon, lat = 85.34, 28.17
    x = int((lon + 180) / 360 * 2**z)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**z)
    image = np.asarray(Image.open(io.BytesIO(module.terrain_png(root / "dem.tif", z, x, y))))
    encoded = image[..., 0].astype(np.uint32) * 65536 + image[..., 1].astype(np.uint32) * 256 + image[..., 2]
    elevations = encoded * 0.1 - 10000
    assert image.shape == (256, 256, 3) and np.any(elevations > 0)
    source = (ROOT / "app/static/map.js").read_text(encoding="utf-8")
    assert "arcgisonline" not in source and "elevation-tiles-prod" not in source


def test_totals_survive_old_results_and_round_trip(tmp_path):
    root = make_mock_run(tmp_path / "mock")
    results = Results.model_validate_json((root / "results.json").read_text(encoding="utf-8"))
    new = Results.model_validate_json(results.model_dump_json())
    assert new.hazard.total_hazard_km2 == results.hazard.total_hazard_km2
    assert new.exposure.total_exposed_buildings == sum(results.exposure.buildings_by_class.values())

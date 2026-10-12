"""Phase-0 contract tests. They must stay green on main at all times (CI gate)."""
import ast
import importlib
import json
from pathlib import Path

import pytest

from cutoff.contracts import ATTRIBUTION, CHANNELS, N_CHANNELS, RASTERS, VECTORS, HazardClass
from cutoff.contracts_check import ContractError, validate_run_dir
from cutoff.geo.grid import Grid, make_grid, utm_epsg

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def mock_run(tmp_path_factory):
    from cutoff.mock import make_mock_run
    return make_mock_run(tmp_path_factory.mktemp("runs") / "demo_mock")


def test_grid_is_utm_and_snapped():
    assert utm_epsg(85.3, 28.1) == 32645
    g = make_grid((85.32, 28.14, 85.36, 28.18))
    assert g.epsg == 32645 and g.transform[0] == 10.0 and g.transform[4] == -10.0
    assert g.transform[2] % 10 == 0 and g.transform[5] % 10 == 0
    w, s, e, n = g.bounds_wgs84()
    assert w <= 85.32 and s <= 28.14 and e >= 85.36 and n >= 28.18


def test_grid_json_roundtrip(tmp_path):
    g = make_grid((85.32, 28.14, 85.36, 28.18))
    g.to_json(tmp_path / "grid.json")
    assert Grid.from_json(tmp_path / "grid.json") == g


def test_channel_contract():
    assert N_CHANNELS == 7 and CHANNELS[4] == "dvv_db" and CHANNELS[-1] == "slope_deg"
    assert HazardClass.NO_OBS == 254


def test_mock_run_satisfies_every_contract(mock_run):
    validate_run_dir(mock_run, require_optional=False)


def test_validator_catches_db_written_as_linear(mock_run, tmp_path):
    import shutil

    import numpy as np
    import rasterio

    bad = tmp_path / "bad"
    shutil.copytree(mock_run, bad)
    with rasterio.open(bad / RASTERS["s1_post"][0], "r+") as ds:
        ds.write(np.full((2, ds.height, ds.width), -12.0, np.float32))
    with pytest.raises(ContractError, match="LINEAR"):
        validate_run_dir(bad, keys=["s1_post"])


def test_results_schema_rejects_post_event_osm(mock_run):
    from cutoff.report.schema import Results
    d = json.loads((mock_run / "results.json").read_text(encoding="utf-8"))
    d["inputs"]["osm_snapshot"] = "2026-08-27T00:00:00Z"
    with pytest.raises(Exception, match="before the event"):
        Results.model_validate(d)


def test_results_schema_requires_attribution(mock_run):
    from cutoff.report.schema import Results
    d = json.loads((mock_run / "results.json").read_text(encoding="utf-8"))
    d["attribution"] = d["attribution"][1:]
    with pytest.raises(Exception, match="attribution"):
        Results.model_validate(d)


def test_attribution_strings_exact():
    assert ATTRIBUTION[0] == "Contains modified Copernicus Sentinel data 2026."
    assert ATTRIBUTION[1].startswith("Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014")
    assert "© OpenStreetMap contributors." in ATTRIBUTION


def test_stage_registry_resolves():
    from cutoff.pipeline import STAGES
    for name, target, keys in STAGES:
        mod, fn = target.split(":")
        assert callable(getattr(importlib.import_module(mod), fn)), name
        assert all(k in RASTERS or k in VECTORS for k in keys), name


BANNED = ["reference/", "EMSR", "emsr", "UNOSAT", "GEOID", "MMFlood", "ImpactMesh", "WorldFloods"]


def test_no_reference_leak():
    """Disqualification guard (PS data rules): pipeline code never imports eval/ or touches reference data."""
    for f in (ROOT / "src").rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", "") or ""]
                assert not any(n == "eval" or n.startswith("eval.") for n in names), f"{f} imports eval"
        for banned in BANNED:
            assert banned not in src, f"{f} mentions {banned}"

"""P2 real-data check script (eval/p2_real_data_check.py) on the synthetic mock run: it only describes a run."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("p2_real_data_check", ROOT / "eval" / "p2_real_data_check.py")
rdc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rdc)

META = {"mean": [-10.8, -17.4, -10.5, -17.1, 0.25, 0.3, 3.2], "std": [3.5, 3.8, 4.2, 4.5, 3.5, 3.8, 3.8],
        "flood_threshold": 0.5}


@pytest.fixture(scope="module")
def mock_run(tmp_path_factory):
    from cutoff.mock import make_mock_run
    return make_mock_run(tmp_path_factory.mktemp("rdc") / "demo_mock")


def test_describe_reports_scores_corridor_s2_and_radiometry(mock_run):
    d, arrays = rdc.describe(mock_run, META)
    assert d["tau"] == 0.5 and 0 < d["valid_frac"] <= 1
    assert set(d["radiometry"]["all_valid"]["channels"]) == {"vv_pre_db", "vh_pre_db", "vv_post_db", "vh_post_db",
                                                              "dvv_db", "dvh_db"}
    pf = d["p_flood"]
    assert 0 <= pf["share_ge_tau"] <= 1 and pf["area_ge_tau_km2"] >= 0
    # the mock flood corridor lies on the low-HAND valley floor, so the corridor scores higher than the scene
    assert d["corridor_hand_le_10m"]["share_ge_tau"] > pf["share_ge_tau"]
    assert set(d["hazard_class_km2"]) == {"1", "2", "3", "4", "5", "254"}
    assert 0 <= d["permanent_on_steep_or_high_hand_km2"] <= d["hazard_class_km2"]["5"]
    s2 = d["s2_check"]
    assert 0 <= s2["share_of_s2_water_model_calls_water"] <= 1 and 0 < s2["clear_frac"] <= 1
    json.dumps(d, default=str)


def test_quicklook_writes_png(mock_run, tmp_path):
    _, arrays = rdc.describe(mock_run, META)
    png = tmp_path / "q.png"
    rdc.quicklook(mock_run, arrays, png, "b0")
    assert png.stat().st_size > 10_000
    assert np.isfinite(arrays[1]).any()

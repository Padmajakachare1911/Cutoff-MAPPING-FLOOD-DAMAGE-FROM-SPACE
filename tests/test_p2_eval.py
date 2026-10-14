"""P2.11 - evaluation harness on a synthetic Kuro Siwo store."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("segmentation_models_pytorch")

from test_p2_training import store  # noqa: E402,F401  (fixture)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("kuro_eval", ROOT / "eval" / "kuro_eval.py")
ke = importlib.util.module_from_spec(spec); spec.loader.exec_module(ke)


def test_b0_and_checkpoint_eval_and_markdown(store, tmp_path):  # noqa: F811
    from cutoff.data.kuro_siwo import KuroSiwoDataset
    from cutoff.ml.train import train
    ck = train(store, tmp_path / "r", {"encoder": "resnet18", "pretrained": False, "epochs": 1, "batch_size": 2,
                                        "num_workers": 0, "max_stat_samples": 10, "name": "unit"})
    ds = KuroSiwoDataset(store, "val", np.zeros(7), np.ones(7))
    rb = ke.evaluate(ds, "b0")
    rm = ke.evaluate(ds, str(ck))
    assert rb["name"] == "b0" and rb["pooled"]["support_px"] > 0
    assert rb["pooled"]["iou"] > 0.5                     # synthetic flood is an obvious dark-change patch
    assert {r["event"] for r in rm["per_event"]} == {"514"}
    cal = ke.calibration(ds, str(ck))
    md = ke.to_markdown([rb, rm], [cal])
    assert "E1" in md and "E2" in md and "E8" in md and "514" in md
    json.dumps([rb, rm], default=float)


def test_calibration_reports_flood_ece_per_slope_bin(store, tmp_path):  # noqa: F811
    """E8 per slope bin (P2.11): one row per bin, counts add up to the pooled flood-ECE sample, markdown table."""
    from cutoff.data.kuro_siwo import KuroSiwoDataset
    from cutoff.ml.train import train
    ck = train(store, tmp_path / "r", {"encoder": "resnet18", "pretrained": False, "epochs": 1, "batch_size": 2,
                                        "num_workers": 0, "max_stat_samples": 10, "name": "unit"})
    ds = KuroSiwoDataset(store, "val", np.zeros(7), np.ones(7))
    cal = ke.calibration(ds, str(ck))
    rows = cal["ece_by_slope"]
    assert [r["slope_bin"] for r in rows] == ["0-5 deg", "5-15 deg", ">=15 deg"]
    assert sum(r["n_px"] for r in rows) == cal["n_flood_ece_px"] > 0
    for r in rows:
        assert (r["n_px"] == 0) == (r["flood_ece"] is None)
        assert r["flood_ece"] is None or 0.0 <= r["flood_ece"] <= 1.0
    md = ke.to_markdown([], [cal])
    assert "E8 - flood ECE by slope stratum" in md and ">=15 deg" in md

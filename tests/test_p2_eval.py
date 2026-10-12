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

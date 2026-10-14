"""VALIDATION-ONLY seed-ensemble check (model-improvement plan, option C). Never reads the test split.

Compares two checkpoints and their mean-probability ensemble by pooled flood IoU on the Kuro Siwo validation
events, sweeping tau. Usage:
    python eval/val_ensemble.py --ckpts models/cutoff_unet_v1.pt C:/cutoff_data/runs/b3_no_slope_seed7/b3_no_slope_seed7.pt \
        --out docs/results/raw/val_ensemble.json
"""
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from kuro_eval import _iter_ckpt  # noqa: E402

from cutoff.contracts import IGNORE_INDEX  # noqa: E402
from cutoff.data.kuro_siwo import KuroSiwoDataset  # noqa: E402

TAUS = np.round(np.arange(0.30, 0.76, 0.05), 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(os.environ.get("CUTOFF_DATA_DIR", "C:/cutoff_data")) / "kuro"))
    ap.add_argument("--ckpts", nargs=2, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ds = KuroSiwoDataset(a.data, "val", np.zeros(7), np.ones(7))
    assert ds.rows[0]["split"] == "val"
    names = ["a", "b", "ensemble"]
    acc = {(n, t, e): np.zeros(3) for n in names for t in TAUS for e in ["ALL"] + sorted(ds.events)}
    its = [_iter_ckpt(ds, c, dev) for c in a.ckpts]
    for (i, pa, y, _), (j, pb, _, _) in zip(*its):
        assert i == j
        valid = y != IGNORE_INDEX
        gt = (y == 2) & valid
        ev = ds.rows[i]["event"]
        for n, p in (("a", pa), ("b", pb), ("ensemble", 0.5 * (pa + pb))):
            f = np.nan_to_num(p[2])
            for t in TAUS:
                pr = (f >= t) & valid
                tp = np.sum(pr & gt)
                c = np.array([tp, np.sum(pr) - tp, np.sum(gt) - tp], dtype=float)  # TP, FP, FN (flood)
                acc[(n, t, "ALL")] += c
                acc[(n, t, ev)] += c
    iou = lambda c: float(c[0] / max(c.sum(), 1))  # noqa: E731
    out = {"ckpts": {"a": a.ckpts[0], "b": a.ckpts[1]}, "split": "val"}
    for n in names:
        curve = {float(t): round(iou(acc[(n, t, "ALL")]), 4) for t in TAUS}
        best = max(curve, key=curve.get)
        out[n] = {"curve": curve, "best_tau": best, "best_iou": curve[best],
                  "per_event_at_best": {e: round(iou(acc[(n, best, e)]), 3) for e in sorted(ds.events)}}
        print(n, "best tau", best, "IoU", curve[best], "per event", out[n]["per_event_at_best"])
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

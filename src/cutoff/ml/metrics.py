"""Confusion-matrix metrics accumulated per event and per slope stratum; calibration error. Owner: P2."""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from cutoff.contracts import IGNORE_INDEX

SLOPE_EDGES = (5.0, 15.0)   # bins: 0 = <5 deg, 1 = 5-15 deg, 2 = >= 15 deg


class ConfusionMeter:
    def __init__(self, n_classes: int = 3):
        self.n = n_classes
        self.cm = np.zeros((n_classes, n_classes), dtype=np.int64)   # rows = truth, cols = prediction

    def update(self, pred, target, mask=None) -> None:
        pred, target = np.asarray(pred).ravel(), np.asarray(target).ravel()
        v = target != IGNORE_INDEX
        if mask is not None:
            v &= np.asarray(mask).ravel().astype(bool)
        idx = target[v].astype(np.int64) * self.n + pred[v].astype(np.int64)
        self.cm += np.bincount(idx, minlength=self.n ** 2).reshape(self.n, self.n)

    def scores(self, cls: int = 2) -> dict:
        tp = self.cm[cls, cls]
        fp = self.cm[:, cls].sum() - tp
        fn = self.cm[cls, :].sum() - tp
        nan = float("nan")
        div = lambda a, b: float(a / b) if b else nan
        ious = [div(self.cm[c, c], self.cm[c, :].sum() + self.cm[:, c].sum() - self.cm[c, c]) for c in range(self.n)]
        return {"precision": div(tp, tp + fp), "recall": div(tp, tp + fn), "f1": div(2 * tp, 2 * tp + fp + fn),
                "iou": div(tp, tp + fp + fn), "miou": float(np.nanmean(ious)) if not np.all(np.isnan(ious)) else nan,
                "support_px": int(self.cm[cls, :].sum())}


def slope_bin(slope_deg) -> np.ndarray:
    return np.digitize(np.nan_to_num(slope_deg), SLOPE_EDGES).astype(np.int8)


class StratifiedMeter:
    """A ConfusionMeter per (event, slope bin) so pooled numbers cannot hide terrain failures."""

    def __init__(self, n_classes: int = 3):
        self.m = defaultdict(lambda: ConfusionMeter(n_classes))

    def update(self, event: str, pred, target, slope_deg) -> None:
        b = slope_bin(slope_deg)
        for k in range(3):
            self.m[(event, k)].update(pred, target, b == k)
            self.m[("ALL", k)].update(pred, target, b == k)
        self.m[(event, "all")].update(pred, target)
        self.m[("ALL", "all")].update(pred, target)

    def table(self) -> list[dict]:
        return [{"event": e, "slope_bin": s, **cm.scores()} for (e, s), cm in sorted(self.m.items(), key=str)]


def expected_calibration_error(conf, correct, n_bins: int = 10) -> float:
    conf, correct = np.asarray(conf, float).ravel(), np.asarray(correct, float).ravel()
    bins = np.minimum((conf * n_bins).astype(int), n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        s = bins == b
        if s.any():
            ece += s.mean() * abs(correct[s].mean() - conf[s].mean())
    return float(ece)

"""Non-learned baseline B0 (Owner: P2) - lets the whole pipeline run before a model is trained.

B0 is the classic SAR change-detection recipe, computed per scene over valid pixels:
    t       = Otsu threshold of post-event VV (dB)
    p_flood = sig((t - VV_post)/1) * sig((-dVV - 3)/1)        dark now AND darkened by > ~3 dB
    p_perm  = sig((t - VV_pre)/1)  * sig((t - VV_post)/1)     dark before AND after
    p_none  = max(0, 1 - p_flood - p_perm); the three are renormalised to sum to 1.
The 1 dB softness turns hard thresholds into pseudo-probabilities so gating (tau = 0.5) works
unchanged. It is a reference baseline (E1), not a tuned method.
"""
from __future__ import annotations

import numpy as np


def otsu(values, bins: int = 256) -> float:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size < 2 or v.min() == v.max():
        return float(v.mean()) if v.size else 0.0
    hist, edges = np.histogram(v, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    w0 = np.cumsum(hist)
    w1 = w0[-1] - w0
    m0 = np.cumsum(hist * centers) / np.maximum(w0, 1)
    m1 = ((hist * centers).sum() - np.cumsum(hist * centers)) / np.maximum(w1, 1)
    between = w0 * w1 * (m0 - m1) ** 2
    # well-separated classes give a flat optimum across the gap: take the middle of the plateau,
    # not its first bin (argmax alone would hug the darker cluster)
    best = np.flatnonzero(between >= between.max() * (1 - 1e-6))
    return float((centers[best[0]] + centers[best[-1]]) / 2)


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def b0_proba(x: np.ndarray) -> np.ndarray:
    """x: (7, H, W) unnormalised input stack (dB channels) -> (3, H, W) float32 probabilities;
    NaN where any SAR channel is missing."""
    vv_pre, vv_post, dvv = x[0], x[2], x[4]
    invalid = ~np.isfinite(x[:6]).all(axis=0)
    t = otsu(vv_post[~invalid])
    with np.errstate(invalid="ignore", over="ignore"):
        pf = _sig(t - vv_post) * _sig(-dvv - 3.0)
        pp = _sig(t - vv_pre) * _sig(t - vv_post)
        pn = np.clip(1.0 - pf - pp, 0.0, None)
        s = pn + pp + pf
        p = np.stack([pn, pp, pf]) / np.where(s > 0, s, 1.0)
    p = p.astype(np.float32)
    p[:, invalid] = np.nan
    return p

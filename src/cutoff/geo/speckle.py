"""Improved Lee sigma speckle filter (Owner: P1, task P1.2).

Lee, J.-S., Wen, J.-H., Ainsworth, T. L., Chen, K.-S., Chen, A. J. (2009). Improved sigma filter for
speckle filtering of SAR imagery. IEEE TGRS 47(1), 202-213. Same parameters as the Kuro Siwo SNAP graph
(Lee Sigma, window 7x7, target 3x3, sigma 0.9); `looks` = 4.4 for Sentinel-1 IW GRDH.

Steps, per pixel (linear intensity in, linear out):
  1. point targets: a pixel whose 3x3 target window holds >= POINT_K pixels above the image's
     `point_pct` percentile is kept unfiltered;
  2. a priori mean x0 = 3x3 MMSE (Lee) estimate; sigma range [a1*x0, a2*x0], where [a1, a2] holds
     `sigma` of the gamma(L, 1/L) speckle mass and has a truncated mean of exactly 1 (unbiased);
  3. MMSE estimate over the 7x7 pixels inside the sigma range, using the truncated speckle CV eta_v.
NaN-safe: NaN pixels stay NaN and are simply left out of every neighbourhood (they never spread).
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

POINT_K = 5  # Lee et al. 2009: K = 5 of the 9 pixels in the 3x3 window above Z98


@lru_cache(maxsize=32)
def sigma_range(looks: float, sigma: float) -> tuple[float, float, float]:
    """(a1, a2, eta_v): speckle interval with probability mass `sigma` and truncated mean 1, plus the
    speckle coefficient of variation inside it. Speckle intensity ~ Gamma(shape=looks, scale=1/looks)."""
    from scipy import optimize, stats

    L = float(looks)
    g0, g1, g2 = (stats.gamma(L + k, scale=1.0 / L) for k in (0, 1, 2))  # v^k p(v) is prop. to g_k

    def bounds(a1):
        return a1, g0.ppf(min(g0.cdf(a1) + sigma, 1.0 - 1e-12))

    def bias(a1):
        lo, hi = bounds(a1)
        return (g1.cdf(hi) - g1.cdf(lo)) / sigma - 1.0

    a1 = optimize.brentq(bias, 1e-9, g0.ppf(1.0 - sigma) * (1 - 1e-9), xtol=1e-12)
    a1, a2 = bounds(a1)
    m2 = (L + 1.0) / L * (g2.cdf(a2) - g2.cdf(a1)) / sigma
    return float(a1), float(a2), float(np.sqrt(max(m2 - 1.0, 0.0)))


def _shifts(size: int):
    r = size // 2
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)]


def _view(padded: np.ndarray, dy: int, dx: int, r: int, h: int, w: int) -> np.ndarray:
    return padded[r + dy:r + dy + h, r + dx:r + dx + w]


def _mmse(z, mean, var, eta):
    """Lee MMSE: x = mean + b (z - mean), b = var_x / var_z, var_x = (var_z - mean^2 eta^2) / (1 + eta^2)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        var_x = (var - mean * mean * eta * eta) / (1.0 + eta * eta)
        b = np.where(var > 0, np.clip(var_x / var, 0.0, 1.0), 0.0)
    return mean + b * (z - mean)


def lee_sigma(img: np.ndarray, window: int = 7, target: int = 3, sigma: float = 0.9,
              looks: float = 4.4, point_pct: float = 98.0) -> np.ndarray:   # linear in, linear out, NaN-safe
    """Improved Lee sigma filter of one linear-intensity band (H, W) -> float32 (H, W)."""
    z = np.asarray(img, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError(f"lee_sigma expects a 2-D band, got shape {z.shape}")
    valid = np.isfinite(z)
    out = np.full(z.shape, np.nan, np.float32)
    if not valid.any():
        return out
    h, w = z.shape
    a1, a2, eta_v = sigma_range(looks, sigma)
    eta0 = 1.0 / np.sqrt(looks)

    r = max(window, target) // 2
    zp = np.pad(np.where(valid, z, np.nan), r, constant_values=np.nan)
    vp = np.isfinite(zp)
    zp0 = np.where(vp, zp, 0.0)

    # 1. point targets
    z98 = np.percentile(z[valid], point_pct)
    bright = vp & (zp0 > z98)
    n_bright = sum(_view(bright, dy, dx, r, h, w).astype(np.int16) for dy, dx in _shifts(target))
    point = valid & (n_bright >= POINT_K)

    # 2. a priori mean: 3x3 MMSE over the valid neighbours
    n = s = ss = 0.0
    for dy, dx in _shifts(target):
        v, x = _view(vp, dy, dx, r, h, w), _view(zp0, dy, dx, r, h, w)
        n = n + v
        s = s + x
        ss = ss + x * x
    with np.errstate(divide="ignore", invalid="ignore"):
        m3 = s / n
        v3 = np.maximum(ss / n - m3 * m3, 0.0)
    prior = _mmse(z, m3, v3, eta0)
    lo, hi = a1 * prior, a2 * prior

    # 3. MMSE over the in-range pixels of the window
    n = s = ss = 0.0
    for dy, dx in _shifts(window):
        x = _view(zp0, dy, dx, r, h, w)
        inr = _view(vp, dy, dx, r, h, w) & (x >= lo) & (x <= hi)
        n = n + inr
        s = s + np.where(inr, x, 0.0)
        ss = ss + np.where(inr, x * x, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        mean = s / n
        var = np.maximum(ss / n - mean * mean, 0.0)
    est = np.where(n > 0, _mmse(z, mean, var, eta_v), prior)

    est = np.where(point, z, est)
    out[valid] = est[valid].astype(np.float32)
    return out

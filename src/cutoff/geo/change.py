"""Stage `disturbance`: scene-adaptive same-track backscatter change in the valley corridor. Owner: P2.

Kuro Siwo labels water only. Debris deposits and scoured channels often RAISE backscatter, smooth
wet mud LOWERS it. We flag statistically unusual same-track change (|z| > k) inside the HAND
corridor, with the noise level estimated in THIS scene from terrain that cannot have flooded,
instead of borrowing fixed dB limits from other events.

D9 (final, after review of split-based change detection, Bovolo & Bruzzone 2007; Martinis et al.
2009): one consistent scene threshold (strata=1 by default; per-pre-VV-tercile sigma is an option),
robust sigma = 1.4826 * MAD, and connected components smaller than `min_px` removed.
Stable-terrain fallback for AOIs without high terrain: HAND > hand_stable -> HAND > corridor -> all
valid pixels (MAD is robust to a minority of changed pixels); the source is reported.
"""
from __future__ import annotations

import numpy as np

from cutoff.contracts import Disturbance
from cutoff.runctx import RunContext

MIN_STABLE_PX = 100


def _robust(v: np.ndarray) -> tuple[float, float]:
    med = float(np.median(v))
    return med, float(1.4826 * np.median(np.abs(v - med)))


def disturbance(d_db, pre_vv_db, hand, valid, k: float = 3.0, hand_corridor_m: float = 60.0,
                hand_stable_m: float = 100.0, strata: int = 1, min_px: int = 20) -> tuple[np.ndarray, dict]:
    """d_db: post - pre change in dB (VV). Returns (int8 Disturbance map, stats)."""
    from scipy import ndimage

    d = np.asarray(d_db, np.float32)
    valid = np.asarray(valid, bool) & np.isfinite(d) & np.isfinite(hand)
    source = None
    for name, cand in ((f"hand>{hand_stable_m:g}", valid & (hand > hand_stable_m)),
                       (f"hand>{hand_corridor_m:g}", valid & (hand > hand_corridor_m)),
                       ("all_valid", valid)):
        if cand.sum() >= MIN_STABLE_PX:
            stable, source = cand, name
            break
    else:
        raise ValueError(f"only {int(valid.sum())} valid pixels - AOI too small or no radar coverage")

    pre = np.asarray(pre_vv_db, np.float32)
    if strata > 1:
        edges = np.nanquantile(pre[stable], np.linspace(0, 1, strata + 1)[1:-1])
        bins = np.digitize(np.nan_to_num(pre, nan=np.nanmedian(pre[stable])), edges)
    else:
        bins = np.zeros(d.shape, np.int64)
    z = np.full(d.shape, np.nan, np.float32)
    sig_by, n_by = [], []
    for b in range(max(strata, 1)):
        sel = stable & (bins == b)
        if sel.sum() < MIN_STABLE_PX:   # sparse stratum: fall back to the pooled estimate
            sel = stable
        med, sig = _robust(d[sel])
        sig = max(sig, 1e-6)
        z[bins == b] = (d[bins == b] - med) / sig
        sig_by.append(sig); n_by.append(int(sel.sum()))

    corridor = valid & (hand <= hand_corridor_m)
    out = np.zeros(d.shape, np.int8)
    for code, mask in ((Disturbance.DECREASE, corridor & (z < -k)), (Disturbance.INCREASE, corridor & (z > k))):
        lab, n = ndimage.label(mask, structure=np.ones((3, 3), bool))
        if n:
            sizes = ndimage.sum(mask, lab, index=np.arange(1, n + 1))
            keep = np.isin(lab, np.flatnonzero(sizes >= min_px) + 1)
            out[keep] = int(code)
    out[~valid] = int(Disturbance.INVALID)
    weights = np.array(n_by, float)
    stats = {"sigma_stable_db": float(np.average(sig_by, weights=weights)), "k_sigma": float(k),
             "n_stable_px": int(stable.sum()), "stable_source": source, "sigma_by_stratum": sig_by,
             "hand_corridor_m": float(hand_corridor_m)}
    return out, stats


def stage_disturbance(ctx: RunContext) -> dict:
    """Reads: s1_pre_mean.tif, s1_post.tif, hand.tif, shadow_layover.tif. Writes: disturb.tif.

    Returns: {"sigma_stable_db": float, "k_sigma": float, "n_stable_px": int}
    """
    from cutoff.geo import raster_io
    from cutoff.geo.sar import to_db

    pre = to_db(raster_io.read(ctx, "s1_pre_mean", squeeze=False)[0])
    post = to_db(raster_io.read(ctx, "s1_post", squeeze=False)[0])
    hand = raster_io.read(ctx, "hand")
    shadow = raster_io.read(ctx, "shadow_layover").astype(bool)
    r = ctx.cfg.get("rules", {})
    out, st = disturbance(post - pre, pre, hand, ~shadow, k=r.get("k_sigma", 3.0),
                          hand_corridor_m=r.get("hand_corridor_m", 60), hand_stable_m=r.get("hand_stable_m", 100),
                          strata=r.get("stable_strata", 1), min_px=r.get("min_component_px", 20))
    if not st["stable_source"].startswith("hand>" + format(r.get("hand_stable_m", 100), "g")):
        ctx.warn("disturbance", f"change-rule noise estimated from '{st['stable_source']}' "
                                "(AOI has little high terrain)")
    raster_io.write(ctx, "disturb", out)
    ctx.log("disturbance", **{k: v for k, v in st.items() if k != "sigma_by_stratum"})
    return {"sigma_stable_db": st["sigma_stable_db"], "k_sigma": st["k_sigma"], "n_stable_px": st["n_stable_px"]}

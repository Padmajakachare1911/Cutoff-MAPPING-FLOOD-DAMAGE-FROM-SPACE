"""Stage `gating`: terrain gating + optional S2 evidence -> hazard classes and flags. Owner: P2.

Implements the truth table in docs/plan/05_contracts.md section 2 (later rules override earlier):
  1 disturb==1 -> 3 (water/smooth mud), disturb==2 -> 4 (roughness/debris)
  2 p_flood >= tau -> 1
  3 class 1 on steep (> slope_max) or high-HAND (> hand_max) terrain -> 2 ("possible")
  4 p_permanent >= tau and not model flood, on flat low terrain (not steep, not high-HAND) -> 5
    (radar back-slopes look dark like water; GFM and OPERA DSWx-S1 also exclude such terrain from reference water)
  5 S2 present: class 2 + clear-sky water -> 1; class 1 + clear-sky no water (and no radar decrease) -> 2
  6 shadow/layover, invalid probabilities or invalid disturbance -> 254
Downgrades never silently delete a detection; the flags record every reason.
"""
from __future__ import annotations

import numpy as np

from cutoff.contracts import Disturbance, Flag, HazardClass as HC
from cutoff.runctx import RunContext


def _u8(*fs) -> np.uint8:
    return np.uint8(sum(int(f) for f in fs))


def gate(probs, dist, slope, hand, shadow_layover, s2_water=None, s2_clear=None, tau: float = 0.5,
         slope_max: float = 15.0, hand_max: float = 30.0) -> tuple[np.ndarray, np.ndarray]:
    H, W = slope.shape
    cls = np.zeros((H, W), np.uint8)
    flags = np.zeros((H, W), np.uint8)
    invalid_p = ~np.isfinite(probs).all(axis=0)
    p_perm = np.nan_to_num(probs[1], nan=0.0)
    p_flood = np.nan_to_num(probs[2], nan=0.0)
    model_flood = (p_flood >= tau) & ~invalid_p
    steep = np.nan_to_num(slope, nan=0.0) > slope_max
    high = np.nan_to_num(hand, nan=0.0) > hand_max
    dec, inc = dist == Disturbance.DECREASE, dist == Disturbance.INCREASE

    flags[model_flood] |= _u8(Flag.MODEL_FLOOD)
    flags[dec] |= _u8(Flag.RULE_DECREASE)
    flags[inc] |= _u8(Flag.RULE_INCREASE)
    flags[steep] |= _u8(Flag.STEEP)
    flags[high] |= _u8(Flag.HIGH_HAND)

    cls[dec] = HC.RULE_DECREASE
    cls[inc] = HC.RULE_INCREASE
    cls[model_flood] = HC.FLOOD_HIGH
    cls[model_flood & (steep | high)] = HC.FLOOD_POSSIBLE
    cls[(p_perm >= tau) & ~model_flood & ~invalid_p & ~(steep | high)] = HC.PERMANENT_WATER

    if s2_water is not None and s2_clear is not None:
        has = s2_clear != 255
        clear = has & (s2_clear == 1)
        water = clear & (s2_water == 1)
        flags[water] |= _u8(Flag.S2_WATER_AGREE)
        flags[clear & ~water] |= _u8(Flag.S2_CLEAR_NO_WATER)
        upgrade = (cls == HC.FLOOD_POSSIBLE) & water
        downgrade = (cls == HC.FLOOD_HIGH) & clear & ~water & ~dec
        cls[upgrade] = HC.FLOOD_HIGH
        cls[downgrade] = HC.FLOOD_POSSIBLE

    sh = np.asarray(shadow_layover, bool)
    flags[sh] |= _u8(Flag.SHADOW_LAYOVER)
    cls[sh | invalid_p | (dist == Disturbance.INVALID)] = HC.NO_OBS
    return cls, flags


def stable_steep_fpr(cls, slope, hand, slope_min: float = 20.0, hand_min: float = 100.0) -> float | None:
    """Share of observable 'cannot-be-flooded' pixels (steep AND far above drainage) called flood (1/2).
    Needs no reference map, so it is computed for every AOI."""
    region = (np.nan_to_num(slope) > slope_min) & (np.nan_to_num(hand) > hand_min) & (cls != HC.NO_OBS)
    if not region.any():
        return None
    return float(np.isin(cls[region], [HC.FLOOD_HIGH, HC.FLOOD_POSSIBLE]).mean())


def stage_gating(ctx: RunContext) -> dict:
    """Reads: p_model, disturb, slope, hand, shadow_layover, (s2_water, s2_clear if present).
    Writes: hazard_class.tif, flags.tif.

    Returns: {"stable_steep_fpr": float | None}
    """
    from cutoff.geo import raster_io

    g = ctx.cfg.get("gating", {})
    tau = float(ctx.summaries.get("model", {}).get("flood_threshold", g.get("p_high", 0.5)))
    probs = raster_io.read(ctx, "p_model", squeeze=False)
    slope, hand = raster_io.read(ctx, "slope"), raster_io.read(ctx, "hand")
    s2w = raster_io.read(ctx, "s2_water") if ctx.has("s2_water") and ctx.has("s2_clear") else None
    s2c = raster_io.read(ctx, "s2_clear") if s2w is not None else None
    cls, flags = gate(probs, raster_io.read(ctx, "disturb"), slope, hand,
                      raster_io.read(ctx, "shadow_layover").astype(bool), s2w, s2c, tau=tau,
                      slope_max=g.get("slope_max_deg", 15.0), hand_max=g.get("hand_max_m", 30.0))
    raster_io.write(ctx, "hazard_class", cls)
    raster_io.write(ctx, "flags", flags)
    fpr = stable_steep_fpr(cls, slope, hand)
    ctx.log("gating", tau=tau, s2_used=s2w is not None, stable_steep_fpr=fpr)
    return {"stable_steep_fpr": fpr}

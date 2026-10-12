"""SAR radiometry shared by training (Kuro Siwo) and inference (pipeline) - Owner: P2.

Kuro Siwo samples and our run-folder rasters are LINEAR sigma0 (verified: Kuro Siwo SNAP graph
calibrates with outputImageScaleInDb=false). Every path converts to dB with the same function,
so training and inference preprocessing cannot drift apart.

D5: no-data (NaN, <= 0) stays NaN - the blueprint mapped it to -30 dB, which makes footprint
gaps look like open water. D6: slope is clipped to SLOPE_CLIP_DEG because Kuro Siwo is
lowland-heavy and steeper slopes are out-of-distribution for the model.
"""
from __future__ import annotations

import warnings

import numpy as np

from cutoff.contracts import CHANNELS, DB_CEIL, DB_FLOOR, SLOPE_CLIP_DEG


def to_db(linear) -> np.ndarray:
    """Linear sigma0 -> dB, finite values clipped to [DB_FLOOR, DB_CEIL]; non-finite or <= 0 -> NaN."""
    lin = np.asarray(linear, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(np.where(lin > 0, lin, np.nan))
    return np.clip(db, DB_FLOOR, DB_CEIL).astype(np.float32)  # np.clip keeps NaN


def pre_mean_linear(pre_stack) -> np.ndarray:
    """(T, 2, H, W) linear pre-event scenes -> (2, H, W) NaN-aware mean in LINEAR units
    (averaging dB biases low). Pixels missing in every scene stay NaN."""
    pre = np.asarray(pre_stack, dtype=np.float32)
    if pre.ndim != 4 or pre.shape[0] < 1:
        raise ValueError(f"expected (T, 2, H, W) with T >= 1, got {pre.shape}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN slices -> NaN, intended
        return np.nanmean(np.where(pre > 0, pre, np.nan), axis=0).astype(np.float32)


def build_input_stack(pre_mean_lin, post_lin, slope_deg) -> np.ndarray:
    """Model input (7, H, W) float32 in contracts.CHANNELS order:
    vv_pre_db, vh_pre_db, vv_post_db, vh_post_db, dvv_db, dvh_db, slope_deg (clipped)."""
    pre = to_db(pre_mean_lin)
    post = to_db(post_lin)
    if pre.shape != post.shape or pre.ndim != 3 or pre.shape[0] != 2:
        raise ValueError(f"pre {pre.shape} and post {post.shape} must both be (2, H, W)")
    slope = np.asarray(slope_deg, dtype=np.float32)
    if slope.shape != pre.shape[1:]:
        raise ValueError(f"slope {slope.shape} must match spatial shape {pre.shape[1:]}")
    slope = np.clip(slope, *SLOPE_CLIP_DEG)
    x = np.concatenate([pre, post, post - pre, slope[None]], axis=0).astype(np.float32)
    assert x.shape[0] == len(CHANNELS)
    return x

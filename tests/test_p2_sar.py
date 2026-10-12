"""P2.2 - SAR input builder shared by training (Kuro Siwo) and inference (pipeline)."""
import numpy as np
import pytest

from cutoff.contracts import CHANNELS, SLOPE_CLIP_DEG
from cutoff.geo.sar import build_input_stack, pre_mean_linear, to_db


def test_to_db_values_and_nodata_stays_nan():
    out = to_db(np.array([0.1, 1.0, 0.0, -1.0, np.nan, 1e-9, 100.0], np.float32))
    assert out[0] == pytest.approx(-10.0) and out[1] == pytest.approx(0.0)
    assert np.isnan(out[2]) and np.isnan(out[3]) and np.isnan(out[4])   # D5: never invent data
    assert out[5] == -30.0 and out[6] == 5.0                              # finite values clipped
    assert out.dtype == np.float32


def test_pre_mean_is_linear_and_nan_aware():
    pre = np.stack([np.full((2, 3, 3), 0.1, np.float32), np.full((2, 3, 3), 0.3, np.float32)])
    pre[1, 0, 0, 0] = np.nan                                              # one pre scene missing a pixel
    m = pre_mean_linear(pre)
    assert m.shape == (2, 3, 3)
    assert m[0, 1, 1] == pytest.approx(0.2)                              # linear mean, not dB mean
    assert m[0, 0, 0] == pytest.approx(0.1)                              # filled from the other scene
    with pytest.raises(ValueError):
        pre_mean_linear(np.zeros((2, 3, 3), np.float32))


def test_stack_order_difference_and_slope_clip():
    pre = np.full((2, 4, 4), 0.1, np.float32)
    post = np.full((2, 4, 4), 0.01, np.float32)
    slope = np.full((4, 4), 40.0, np.float32)
    x = build_input_stack(pre, post, slope)
    assert x.shape == (len(CHANNELS), 4, 4) and x.dtype == np.float32
    assert np.allclose(x[4], x[2] - x[0]) and np.allclose(x[4], -10.0)
    assert np.allclose(x[6], SLOPE_CLIP_DEG[1])                          # D6: 40 deg -> 15 deg


def test_nan_post_propagates_to_change_channels():
    pre = np.full((2, 4, 4), 0.1, np.float32)
    post = np.full((2, 4, 4), 0.05, np.float32)
    post[0, 1, 1] = np.nan
    x = build_input_stack(pre, post, np.zeros((4, 4), np.float32))
    assert np.isnan(x[2, 1, 1]) and np.isnan(x[4, 1, 1])
    assert np.isfinite(x[0, 1, 1]) and np.isfinite(x[6, 1, 1])


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        build_input_stack(np.zeros((2, 4, 4)), np.zeros((2, 5, 4)), np.zeros((4, 4)))
    with pytest.raises(ValueError):
        build_input_stack(np.zeros((2, 4, 4)), np.zeros((2, 4, 4)), np.zeros((3, 4)))

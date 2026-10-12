"""P1.2 - improved Lee sigma filter (Lee et al. 2009)."""
import numpy as np
import pytest

from cutoff.geo.speckle import lee_sigma, sigma_range

LOOKS = 4.4


def speckled(mean, shape, seed=0, looks=LOOKS):
    rng = np.random.default_rng(seed)
    return (np.asarray(mean, np.float64) * rng.gamma(looks, 1.0 / looks, shape)).astype(np.float32)


def cv(a):
    a = a[np.isfinite(a)]
    return a.std() / a.mean()


def test_sigma_range_is_unbiased_and_holds_sigma_mass():
    from scipy import stats

    a1, a2, eta = sigma_range(LOOKS, 0.9)
    g = stats.gamma(LOOKS, scale=1.0 / LOOKS)
    assert g.cdf(a2) - g.cdf(a1) == pytest.approx(0.9, abs=1e-4)
    mean_in = (stats.gamma(LOOKS + 1, scale=1.0 / LOOKS).cdf(a2)
               - stats.gamma(LOOKS + 1, scale=1.0 / LOOKS).cdf(a1)) / 0.9
    assert mean_in == pytest.approx(1.0, abs=1e-4)
    assert a1 < 1 < a2 and 0 < eta < 1 / np.sqrt(LOOKS)


def test_flat_field_cv_drops_below_40_percent():
    img = speckled(0.08, (200, 200))
    out = lee_sigma(img)
    assert out.dtype == np.float32 and out.shape == img.shape
    assert cv(out[10:-10, 10:-10]) < 0.4 * cv(img[10:-10, 10:-10])


def test_step_edge_keeps_side_means():
    img = np.empty((160, 160), np.float32)
    img[:, :80] = speckled(0.02, (160, 80), seed=1)
    img[:, 80:] = speckled(0.20, (160, 80), seed=2)
    out = lee_sigma(img)
    for sl, true in ((np.s_[:, :80], 0.02), (np.s_[:, 80:], 0.20)):
        assert out[sl].mean() == pytest.approx(true, rel=0.05)
        assert out[sl].mean() == pytest.approx(img[sl].mean(), rel=0.05)
    # still a step: the columns next to the edge stay on their own side
    assert out[:, 76:79].mean() < 0.06 and out[:, 81:84].mean() > 0.14


def test_bright_point_target_survives():
    img = speckled(0.05, (101, 101), seed=3)
    img[49:52, 49:52] = 20.0           # a 3x3 point target (a corner reflector spreads over a few pixels in GRD)
    out = lee_sigma(img)
    assert out[50, 50] == img[50, 50]  # kept unfiltered
    assert out[50, 50] > 100 * np.median(out)


def test_nan_stays_nan_and_does_not_spread():
    img = speckled(0.08, (120, 120), seed=4)
    ref = lee_sigma(img)
    holed = img.copy()
    holed[60, 60] = np.nan
    holed[10:14, 100:104] = np.nan
    out = lee_sigma(holed)
    assert np.array_equal(np.isnan(out), np.isnan(holed))   # NaN stays NaN; no new NaN
    far = np.ones_like(img, bool)
    far[60 - 4:60 + 5, 60 - 4:60 + 5] = False
    far[10 - 4:14 + 4, 100 - 4:104 + 4] = False
    np.testing.assert_allclose(out[far], ref[far], rtol=1e-5)  # pixels outside the 7x7 reach are unchanged


def test_all_nan_and_zero_inputs():
    assert np.isnan(lee_sigma(np.full((20, 20), np.nan, np.float32))).all()
    z = np.zeros((20, 20), np.float32)
    assert np.array_equal(lee_sigma(z), z)

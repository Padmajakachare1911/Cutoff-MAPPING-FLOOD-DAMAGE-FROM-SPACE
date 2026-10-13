"""P2.7-P2.9 - disturbance rule, gating truth table, vectorisation (+ stage runs on the mock run)."""
import shutil
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
import rasterio
import yaml
from rasterio.transform import from_origin

from cutoff.contracts import Flag, HazardClass as HC
from cutoff.contracts_check import validate_run_dir
from cutoff.geo.change import disturbance, stage_disturbance
from cutoff.geo.gating import gate, stage_gating, stable_steep_fpr
from cutoff.geo.grid import Grid
from cutoff.geo.vectorize import class_areas_km2, stage_vectorize
from cutoff.runctx import RunContext

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mock_src(tmp_path_factory):
    from cutoff.mock import make_mock_run
    return make_mock_run(tmp_path_factory.mktemp("m") / "demo_mock")


@pytest.fixture
def ctx(mock_src, tmp_path):
    run = tmp_path / "run"
    shutil.copytree(mock_src, run)
    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text())
    c = RunContext(run_dir=run, run_id="t", aoi_bbox=(85.32, 28.14, 85.36, 28.18),
                   event_datetime=datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc),
                   osm_snapshot="2026-07-27T00:00:00Z", mode="cached", cfg=cfg, grid=Grid.from_json(run / "grid.json"))
    c.summaries["model"] = {"flood_threshold": 0.5}
    return c


# ----------------------------------------------------------------- disturbance
def _scene():
    rng = np.random.default_rng(0)
    d = rng.normal(0, 1, (100, 100)).astype(np.float32)
    hand = np.full((100, 100), 200.0, np.float32)
    hand[40:60] = 5.0                                   # valley corridor
    d[45:50, 10:20] = -8                                # water / smooth mud
    d[52:55, 10:20] = +8                                # debris
    return d, hand


def test_disturbance_flags_both_signs_in_corridor_only():
    d, hand = _scene()
    d[5:10, 10:20] = -8                                 # same change on a ridge: outside corridor
    out, st = disturbance(d, np.full_like(d, -10), hand, np.ones_like(d, bool))
    assert (out[45:50, 10:20] == 1).all() and (out[52:55, 10:20] == 2).all()
    assert (out[5:10, 10:20] == 0).all()
    assert st["sigma_stable_db"] < 1.5 and st["k_sigma"] == 3.0 and st["stable_source"] == "hand>100"


def test_disturbance_removes_small_specks_and_marks_invalid():
    d, hand = _scene()
    d[42:45, 70:73] = -9                                # 9-px speck < min_px
    valid = np.ones_like(d, bool); valid[0, 0] = False
    out, _ = disturbance(d, np.full_like(d, -10), hand, valid, min_px=20)
    assert (out[42:45, 70:73] == 0).all() and out[0, 0] == -1


def test_disturbance_falls_back_on_lowlands():
    d, _ = _scene()
    flat = np.full_like(d, 3.0)                         # lowland: no HAND > 100 m anywhere
    out, st = disturbance(d, np.full_like(d, -10), flat, np.ones_like(d, bool))
    assert st["stable_source"] == "all_valid" and (out[45:50, 10:20] == 1).all()


def test_disturbance_optional_strata():
    rng = np.random.default_rng(1)
    pre = np.where(np.arange(100)[:, None] < 50, -6.0, -16.0) * np.ones((100, 100))
    d = np.where(pre > -10, rng.normal(0, 0.5, (100, 100)), rng.normal(0, 3.0, (100, 100))).astype(np.float32)
    hand = np.full((100, 100), 200.0)
    _, st1 = disturbance(d, pre, hand, np.ones((100, 100), bool), strata=1)
    _, st3 = disturbance(d, pre, hand, np.ones((100, 100), bool), strata=3)
    assert st3["sigma_by_stratum"][0] != pytest.approx(st3["sigma_by_stratum"][-1], rel=0.5)
    assert len(st1["sigma_by_stratum"]) == 1


# ----------------------------------------------------------------- gating truth table
def _inputs(n=10):
    probs = np.zeros((3, n, n), np.float32); probs[0] = 1.0
    z = lambda v=0: np.full((n, n), v, np.float32)
    return probs, np.zeros((n, n), np.int8), z(), z(), np.zeros((n, n), bool)


def _set(probs, r, c, p):
    probs[:, r, c] = p


def test_gating_truth_table():
    probs, dist, slope, hand, sh = _inputs()
    _set(probs, 0, 0, [0.1, 0.1, 0.8])                          # model flood, flat -> 1
    _set(probs, 0, 1, [0.1, 0.1, 0.8]); slope[0, 1] = 30        # model flood, steep -> 2
    _set(probs, 0, 2, [0.1, 0.1, 0.8]); hand[0, 2] = 50         # model flood, high HAND -> 2
    _set(probs, 0, 3, [0.1, 0.8, 0.1])                          # permanent -> 5
    dist[0, 4] = 1                                              # rule decrease -> 3
    dist[0, 5] = 2                                              # rule increase -> 4
    _set(probs, 0, 6, [0.1, 0.1, 0.8]); dist[0, 6] = 2          # model flood beats rule -> 1
    sh[0, 7] = True; _set(probs, 0, 7, [0.1, 0.1, 0.8])         # shadow -> 254
    dist[0, 8] = -1                                             # invalid -> 254
    probs[:, 0, 9] = np.nan                                     # no data -> 254
    cls, flags = gate(probs, dist, slope, hand, sh)
    assert cls[0].tolist() == [1, 2, 2, 5, 3, 4, 1, 254, 254, 254]
    assert flags[0, 1] & Flag.MODEL_FLOOD and flags[0, 1] & Flag.STEEP
    assert flags[0, 2] & Flag.HIGH_HAND and flags[0, 6] & Flag.RULE_INCREASE
    assert flags[0, 7] & Flag.SHADOW_LAYOVER and cls[1, 1] == HC.NONE


def test_gating_permanent_water_needs_flat_low_terrain():
    """Rule 4 uses the same terrain test as rule 3: radar back-slopes look dark like water, so p_permanent on
    steep or high-HAND terrain is not class 5 (GFM/OPERA apply terrain exclusion to reference water too)."""
    probs, dist, slope, hand, sh = _inputs()
    _set(probs, 0, 0, [0.1, 0.8, 0.1])                          # flat, low -> 5
    _set(probs, 0, 1, [0.1, 0.8, 0.1]); slope[0, 1] = 40        # back-slope -> not water
    _set(probs, 0, 2, [0.1, 0.8, 0.1]); hand[0, 2] = 300        # high above drainage -> not water
    _set(probs, 0, 3, [0.1, 0.8, 0.1]); slope[0, 3] = 40; dist[0, 3] = 1  # steep: the rule decrease shows again
    cls, flags = gate(probs, dist, slope, hand, sh)
    assert cls[0, :4].tolist() == [5, 0, 0, 3]
    assert flags[0, 1] & Flag.STEEP and flags[0, 2] & Flag.HIGH_HAND   # the reason stays recorded


def test_gating_s2_upgrade_and_downgrade():
    probs, dist, slope, hand, sh = _inputs()
    _set(probs, 0, 0, [0.1, 0.1, 0.8]); slope[0, 0] = 30        # possible ...
    _set(probs, 0, 1, [0.1, 0.1, 0.8])                          # high ...
    _set(probs, 0, 2, [0.1, 0.1, 0.8]); dist[0, 2] = 1          # high + rule decrease
    water = np.zeros((10, 10), np.uint8); water[0, 0] = 1
    clear = np.ones((10, 10), np.uint8); clear[5:] = 255        # bottom half: no S2 data
    cls, flags = gate(probs, dist, slope, hand, sh, s2_water=water, s2_clear=clear)
    assert cls[0, 0] == 1 and flags[0, 0] & Flag.S2_WATER_AGREE  # ... upgraded by S2 water
    assert cls[0, 1] == 2 and flags[0, 1] & Flag.S2_CLEAR_NO_WATER  # ... downgraded by clear S2
    assert cls[0, 2] == 1                                       # not downgraded: radar saw a decrease


def test_gating_permanent_water_contradicted_by_clear_s2_is_dropped():
    """Rule 5 extension: class 5 where clear-sky S2 sees no water is not permanent water (dry sand and smooth
    soil look dark to radar like water, e.g. Deir ez-Zor desert). Without S2 data the radar call stays."""
    probs, dist, slope, hand, sh = _inputs()
    for c in range(4):
        _set(probs, 0, c, [0.1, 0.8, 0.1])                      # permanent by the model
    dist[0, 3] = 1                                              # ... with a radar decrease underneath
    water = np.zeros((10, 10), np.uint8); water[0, 0] = 1
    clear = np.ones((10, 10), np.uint8); clear[0, 2] = 0; clear[5:] = 255
    _set(probs, 6, 0, [0.1, 0.8, 0.1])                          # bottom half: no S2 data
    cls, flags = gate(probs, dist, slope, hand, sh, s2_water=water, s2_clear=clear)
    assert cls[0, :4].tolist() == [5, 0, 5, 3]  # S2 water -> 5; S2 clear dry -> 0; cloudy -> 5; dry -> rule 3
    assert cls[6, 0] == 5
    assert flags[0, 1] & Flag.S2_CLEAR_NO_WATER


def test_stable_steep_fpr():
    cls = np.array([[1, 0, 2, 254]], np.uint8)
    slope = np.array([[30, 30, 30, 30]], np.float32); hand = np.array([[200, 200, 200, 200]], np.float32)
    assert stable_steep_fpr(cls, slope, hand) == pytest.approx(2 / 3)
    assert stable_steep_fpr(cls, slope * 0, hand) is None


# ----------------------------------------------------------------- vectorise
def test_class_areas_need_utm():
    cls = np.ones((100, 100), np.uint8)
    tr = from_origin(300000, 3110000, 10, 10)
    assert class_areas_km2(cls, tr, "EPSG:32645")[1] == pytest.approx(1.0)
    with pytest.raises(ValueError):
        class_areas_km2(cls, tr, "EPSG:3857")


# ----------------------------------------------------------------- stages on the mock run
def test_stages_on_mock_run(ctx):
    st = stage_disturbance(ctx)
    assert {"sigma_stable_db", "k_sigma", "n_stable_px"} <= set(st)
    g = stage_gating(ctx)
    assert "stable_steep_fpr" in g
    v = stage_vectorize(ctx)
    validate_run_dir(ctx.run_dir, keys=["disturb", "hazard_class", "flags", "hazard"])
    assert v["area_km2_by_class"]["flood_high"] > 0 and v["no_observation_km2"] > 0
    hz = gpd.read_file(ctx.path("hazard"), layer="hazard")
    assert set(hz["class"]) <= {1, 2, 3, 4} and (hz.area > 0).all()
    with rasterio.open(ctx.path("hazard_class")) as ds:
        assert ds.read(1)[25, ctx.grid.width - 40] == HC.NO_OBS   # mock shadow patch


def test_vectorize_empty_hazard(ctx):
    with rasterio.open(ctx.path("hazard_class"), "r+") as ds:
        ds.write(np.zeros((1, ds.height, ds.width), np.uint8))
    v = stage_vectorize(ctx)
    assert v["no_observation_km2"] == 0
    assert len(gpd.read_file(ctx.path("hazard"), layer="hazard")) == 0
    validate_run_dir(ctx.run_dir, keys=["hazard"])

"""P1.4 - stage_s1 with a fake backend (deterministic arrays) and the recorded STAC fixture."""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from cutoff.contracts_check import ContractError, validate_run_dir
from cutoff.data import s1_acquire
from cutoff.data.s1_pairs import NoValidPair
from cutoff.geo.grid import make_grid
from cutoff.runctx import RunContext

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
ITEMS = json.loads((ROOT / "tests" / "fixtures" / "stac_trishuli_s1.json").read_text(encoding="utf-8"))
BBOX = (85.33, 28.15, 85.35, 28.17)
EVENT = datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc)
S1_KEYS = ["s1_pre_mean", "s1_post", "lia", "shadow_layover"]
# deterministic linear VV per scene date (constant fields: lee_sigma of a constant is that constant)
VV = {"2026-08-28": 0.02, "2026-08-16": 0.05, "2026-08-04": 0.07, "2026-07-23": 0.09}


def make_ctx(tmp_path, mode="fast", cache=None, name="run"):
    g = make_grid(BBOX)
    run = tmp_path / name
    run.mkdir(parents=True)
    g.to_json(run / "grid.json")
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["run"]["cache_dir"] = str(cache or tmp_path / "cache")
    return RunContext(run_dir=run, run_id=name, aoi_bbox=BBOX, event_datetime=EVENT,
                      osm_snapshot="2026-07-27T00:00:00Z", mode=mode, cfg=cfg, grid=g)


class FakeBackend:
    def __init__(self, holes=None, db=False):
        self.calls = []
        self.holes = holes or {}
        self.db = db

    def __call__(self, scene, grid, ctx):
        self.calls.append(scene.id)
        day = scene.datetime.date().isoformat()
        h, w = grid.height, grid.width
        vv = np.full((h, w), VV[day], np.float32)
        vh = vv / 5
        lia = np.full((h, w), 40.0, np.float32)
        lia[:5, :5] = 95.0      # layover-like geometry
        lia[5:10, :5] = -2.0
        dm = np.ones((h, w), np.float32)
        dm[-3:, :] = 0          # footprint edge
        for (r0, r1, c0, c1) in self.holes.get(day, []):
            dm[r0:r1, c0:c1] = 0
        arr = np.stack([vv, vh, lia, dm])
        if self.db:
            arr[:2] = 10 * np.log10(arr[:2])
        arr[:3, dm == 0] = 0.0  # Sentinel Hub returns 0 outside the data mask
        return arr


@pytest.fixture
def fake(monkeypatch):
    fb = FakeBackend(holes={"2026-08-16": [(50, 60, 50, 60)]})
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", fb)
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: ITEMS)
    return fb


def read(ctx, key):
    import rasterio
    with rasterio.open(ctx.path(key)) as ds:
        return ds.read()


def test_stage_writes_contract_valid_files(tmp_path, fake):
    ctx = make_ctx(tmp_path)
    out = s1_acquire.stage_s1(ctx)
    validate_run_dir(ctx.run_dir, keys=S1_KEYS)
    assert out["s1_backend"] == "sentinelhub" and out["rel_orbit"] == 85 and out["orbit_direction"] == "ascending"
    assert out["s1_post"]["id"].startswith("S1D_IW_GRDH_1SDV_20260828T122141")
    assert set(out["s1_post"]) >= {"id", "datetime", "platform"} and out["s1_post"]["platform"] == "sentinel-1d"
    assert [p["datetime"][:10] for p in out["s1_pre"]] == ["2026-08-16", "2026-08-04", "2026-07-23"]
    assert out["post_lag_hours"] == pytest.approx(57.5, abs=0.05)
    assert len(fake.calls) == 4
    pairs = json.loads(ctx.path("pairs").read_text(encoding="utf-8"))
    assert pairs["chosen"]["post"]["id"] == out["s1_post"]["id"] and len(pairs["candidates"]) >= 1
    post, pre, lia, sl = read(ctx, "s1_post"), read(ctx, "s1_pre_mean"), read(ctx, "lia")[0], read(ctx, "shadow_layover")[0]
    assert np.allclose(post[0][:-3], 0.02) and np.allclose(post[1][:-3], 0.004)
    assert np.isnan(post[:, -3:]).all() and np.isnan(lia[-3:]).all()           # dataMask = 0 -> NaN
    assert np.isclose(pre[0, 20, 20], 0.07) and np.isnan(pre[:, -3:]).all()      # linear mean of 0.05/0.07/0.09
    # shadow/layover: LIA <= 0 or >= 90 on valid pixels only
    assert sl[:10, :5].all() and sl[10:-3].sum() == 0 and sl[-3:].sum() == 0
    log = [json.loads(l) for l in ctx.path("run_log").read_text(encoding="utf-8").splitlines()]
    assert any(r["stage"] == "s1" for r in log)


def test_nan_in_one_pre_scene_is_filled_by_the_others(tmp_path, fake):
    ctx = make_ctx(tmp_path)
    s1_acquire.stage_s1(ctx)
    pre = read(ctx, "s1_pre_mean")
    assert np.allclose(pre[0, 20, 20], (0.05 + 0.07 + 0.09) / 3, rtol=1e-5)
    assert np.isfinite(pre[:, 50:60, 50:60]).all()                              # hole only in 08-16
    assert np.allclose(pre[0, 50:60, 50:60], (0.07 + 0.09) / 2, rtol=1e-5)    # linear mean of the other two


def test_db_is_never_written(tmp_path, monkeypatch):
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", FakeBackend(db=True))
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: ITEMS)
    ctx = make_ctx(tmp_path)
    with pytest.raises(ValueError, match="linear"):
        s1_acquire.stage_s1(ctx)
    assert not ctx.path("s1_post").exists()
    # and the validator rejects dB on disk if anything ever wrote it
    import rasterio
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", FakeBackend())
    s1_acquire.stage_s1(ctx)
    with rasterio.open(ctx.path("s1_post"), "r+") as ds:
        ds.write(np.full((2, ds.height, ds.width), -15.0, np.float32))
    with pytest.raises(ContractError, match="LINEAR"):
        validate_run_dir(ctx.run_dir, keys=["s1_post"])


def test_low_valid_coverage_warns(tmp_path, monkeypatch):
    fb = FakeBackend(holes={d: [(0, 150, 0, 300)] for d in VV})
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", fb)
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: ITEMS)
    ctx = make_ctx(tmp_path)
    s1_acquire.stage_s1(ctx)
    assert any("valid" in w and "%" in w for w in ctx.warnings)


def test_cache_is_written_and_reused_in_cached_mode(tmp_path, fake, monkeypatch):
    cache = tmp_path / "cache"
    ctx_fast = make_ctx(tmp_path, cache=cache, name="fast")
    s1_acquire.stage_s1(ctx_fast)
    files = sorted(p.relative_to(cache).as_posix() for p in (cache / "s1").rglob("*.tif"))
    gh = s1_acquire.grid_hash(make_grid(BBOX))
    assert len(files) == 4 and all(f.endswith(f"/{gh}.tif") for f in files)
    # fast mode again: served from the cache, backend not called
    n = len(fake.calls)
    s1_acquire.stage_s1(make_ctx(tmp_path, cache=cache, name="fast2"))
    assert len(fake.calls) == n
    # cached mode: no search, no backend
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: pytest.fail("cached mode must not search"))
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", lambda *a: pytest.fail("cached mode must not fetch"))
    ctx = make_ctx(tmp_path, mode="cached", cache=cache, name="cached")
    out = s1_acquire.stage_s1(ctx)
    assert out["s1_backend"] == "cached"
    validate_run_dir(ctx.run_dir, keys=S1_KEYS)
    for key in ("s1_post", "s1_pre_mean", "lia", "shadow_layover"):
        np.testing.assert_array_equal(read(ctx, key), read(ctx_fast, key))


def test_cached_mode_without_cache_raises_cache_miss(tmp_path, monkeypatch):
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: pytest.fail("cached mode must not search"))
    with pytest.raises(s1_acquire.CacheMiss, match="cache_aoi"):
        s1_acquire.stage_s1(make_ctx(tmp_path, mode="cached"))


def test_no_same_track_pair_raises(tmp_path, monkeypatch):
    only_post = [it for it in ITEMS if "20260828T" in it["id"] or "_20260824T" in it["id"]]
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: only_post)
    monkeypatch.setitem(s1_acquire.BACKENDS, "sentinelhub", FakeBackend())
    ctx = make_ctx(tmp_path)
    with pytest.raises(NoValidPair):
        s1_acquire.stage_s1(ctx)
    assert "error" in json.loads(ctx.path("pairs").read_text(encoding="utf-8"))

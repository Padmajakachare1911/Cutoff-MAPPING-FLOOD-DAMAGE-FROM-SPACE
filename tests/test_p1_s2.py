"""P1.6 - Sentinel-2 evidence stage: synthetic SCL/bands (water, cloud, snow), no-scene and cloudy cases."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from cutoff.contracts_check import validate_run_dir
from cutoff.data import s2 as s2mod
from cutoff.data import sentinelhub as sh
from cutoff.geo.grid import Grid, make_grid
from cutoff.runctx import RunContext

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
BBOX = (85.33, 28.15, 85.35, 28.17)
EVENT = datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc)
POST = "2026-08-28T12:21:41.762029Z"
NO_SCENE = "Sentinel-2: no clear scene within ±5 days"


def make_ctx(tmp_path, mode="fast"):
    g = make_grid(BBOX)
    run = tmp_path / "run"
    run.mkdir()
    g.to_json(run / "grid.json")
    (run / "pairs.json").write_text(json.dumps({"chosen": {"post": {"id": "S1D_POST", "datetime": POST}}}))
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    return RunContext(run_dir=run, run_id="t", aoi_bbox=BBOX, event_datetime=EVENT,
                      osm_snapshot="2026-07-27T00:00:00Z", mode=mode, cfg=cfg, grid=g)


def bands(h, w, scl_value=4, b03=0.05, b11=0.20):
    return np.stack([np.full((h, w), b03), np.full((h, w), b11), np.full((h, w), scl_value),
                     np.ones((h, w))]).astype(np.float32)


def test_layers_water_cloud_snow_nodata():
    # columns: open water, vegetation, cloud, snow (bright in green, dark in SWIR -> MNDWI > 0), cloud shadow
    b03 = np.array([[0.10, 0.05, 0.40, 0.80, 0.03, 0.10]], np.float32)
    b11 = np.array([[0.02, 0.20, 0.35, 0.10, 0.02, 0.02]], np.float32)
    scl = np.array([[6, 4, 9, 11, 3, 6]], np.float32)
    dm = np.array([[1, 1, 1, 1, 1, 0]], np.float32)
    water, clear, frac = s2mod.s2_layers(b03, b11, scl, dm, clear_scl=(4, 5, 6, 7), mndwi_threshold=0.0)
    assert water.dtype == np.uint8 and clear.dtype == np.uint8
    assert clear.tolist() == [[1, 1, 0, 0, 0, 255]]
    assert water.tolist() == [[1, 0, 0, 0, 0, 255]]       # snow is never "clear", so never water (D11)
    assert frac == pytest.approx(2 / 6)


def test_mndwi_zero_denominator_is_not_water():
    z = np.zeros((1, 2), np.float32)
    water, clear, _ = s2mod.s2_layers(z, z, np.full((1, 2), 6, np.float32), np.ones((1, 2), np.float32))
    assert water.tolist() == [[0, 0]] and clear.tolist() == [[1, 1]]


def test_stage_writes_contract_files(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    g = ctx.grid
    arr = bands(g.height, g.width)
    arr[0, :50], arr[1, :50], arr[2, :50] = 0.1, 0.02, 6       # a lake
    arr[2, -40:] = 9                                           # clouds
    arr[3, :, :3] = 0                                          # outside the data mask
    seen = {}

    def fake(grid, around, days, cfg, **kw):
        seen.update(around=around, days=days, after=kw.get("after"))
        return arr, "S2C_MSIL2A_20260829T044701_N0512_R076_T45RUM_20260829T095112"

    monkeypatch.setattr(sh, "fetch_s2_best", fake)
    out = s2mod.stage_s2(ctx)
    assert seen == {"around": datetime(2026, 8, 28, 12, 21, 41, 762029, tzinfo=timezone.utc), "days": 5, "after": EVENT}
    assert out["s2_scenes"] == ["S2C_MSIL2A_20260829T044701_N0512_R076_T45RUM_20260829T095112"]
    validate_run_dir(ctx.run_dir, keys=["s2_water", "s2_clear"], require_optional=True)
    import rasterio
    with rasterio.open(ctx.path("s2_water")) as a, rasterio.open(ctx.path("s2_clear")) as b:
        water, clear = a.read(1), b.read(1)
    assert (water[:50, 3:] == 1).all() and (water[60:-40, 3:] == 0).all()
    assert (clear[-40:, 3:] == 0).all() and (clear[:, :3] == 255).all() and (water[:, :3] == 255).all()
    expect = float((clear == 1).sum()) / clear.size
    assert out["s2_clear_fraction"] == pytest.approx(expect, abs=1e-4)
    assert not ctx.warnings


def test_no_scene_returns_empty_and_warns(tmp_path, monkeypatch):
    monkeypatch.setattr(sh, "fetch_s2_best", lambda *a, **k: None)
    ctx = make_ctx(tmp_path)
    assert s2mod.stage_s2(ctx) == {"s2_scenes": [], "s2_clear_fraction": None}
    assert ctx.warnings == [NO_SCENE]
    assert not ctx.path("s2_water").exists() and not ctx.path("s2_clear").exists()
    validate_run_dir(ctx.run_dir, keys=["s2_water", "s2_clear"])  # optional files may be absent


def test_all_cloud_counts_as_no_clear_scene(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(sh, "fetch_s2_best",
                        lambda *a, **k: (bands(ctx.grid.height, ctx.grid.width, scl_value=9), "S2X"))
    assert s2mod.stage_s2(ctx) == {"s2_scenes": [], "s2_clear_fraction": None}
    assert ctx.warnings == [NO_SCENE] and not ctx.path("s2_water").exists()


def test_errors_never_fail_the_stage(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise sh.MissingCredentials("Sentinel Hub credentials missing")

    monkeypatch.setattr(sh, "fetch_s2_best", boom)
    ctx = make_ctx(tmp_path)
    assert s2mod.stage_s2(ctx) == {"s2_scenes": [], "s2_clear_fraction": None}
    assert len(ctx.warnings) == 1 and ctx.warnings[0].startswith("Sentinel-2") and "credentials" in ctx.warnings[0]


def test_disabled_or_missing_pairs(tmp_path):
    ctx = make_ctx(tmp_path)
    ctx.path("pairs").unlink()
    assert s2mod.stage_s2(ctx) == {"s2_scenes": [], "s2_clear_fraction": None} and ctx.warnings
    (tmp_path / "x").mkdir()
    ctx2 = make_ctx(tmp_path / "x")
    ctx2.cfg["s2"]["enabled"] = False
    assert s2mod.stage_s2(ctx2) == {"s2_scenes": [], "s2_clear_fraction": None}


def test_cached_mode_reuses_the_cache(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path)
    monkeypatch.setattr(sh, "fetch_s2_best", lambda *a, **k: (bands(ctx.grid.height, ctx.grid.width, scl_value=6,
                                                                       b03=0.1, b11=0.02), "S2A"))
    first = s2mod.stage_s2(ctx)
    monkeypatch.setattr(sh, "fetch_s2_best", lambda *a, **k: pytest.fail("cached mode must not fetch"))
    (tmp_path / "c").mkdir()
    ctx2 = make_ctx(tmp_path / "c", mode="cached")
    ctx2.cfg["run"]["cache_dir"] = ctx.cfg["run"]["cache_dir"]
    assert s2mod.stage_s2(ctx2) == first
    validate_run_dir(ctx2.run_dir, keys=["s2_water", "s2_clear"], require_optional=True)
    (tmp_path / "d").mkdir()
    ctx3 = make_ctx(tmp_path / "d", mode="cached")   # empty cache -> warning, never an error
    assert s2mod.stage_s2(ctx3) == {"s2_scenes": [], "s2_clear_fraction": None} and ctx3.warnings


# ---------------------------------------------------------------- fetch_s2_best (mocked STAC + Process API)
def _tiff_on(grid: Grid, arr: np.ndarray) -> bytes:
    from rasterio.io import MemoryFile

    with MemoryFile() as mf:
        with mf.open(driver="GTiff", width=grid.width, height=grid.height, count=arr.shape[0], dtype="float32",
                     crs=grid.crs, transform=grid.affine) as ds:
            ds.write(arr.astype(np.float32))
        return mf.read()


def _item(dt):
    return {"id": f"S2X_MSIL2A_{dt:%Y%m%dT%H%M%S}_T45RUM", "properties": {"datetime": dt.isoformat().replace("+00:00", "Z")}}


def test_fetch_s2_best_picks_most_clear_post_event_date(monkeypatch):
    around = datetime(2026, 8, 28, 12, 21, tzinfo=timezone.utc)
    dates = [datetime(2026, 8, d, 4, 50, tzinfo=timezone.utc) for d in (24, 27, 29, 31)]
    monkeypatch.setattr(sh, "search_items", lambda bbox, start, end, url, collection, **k:
                        [_item(d) for d in dates if start <= d <= end])
    clear_by_day = {"2026-08-24": 1.0, "2026-08-27": 0.2, "2026-08-29": 0.7, "2026-08-31": 0.4}
    requested = []

    def fake_post(url, body, token):
        day = body["input"]["data"][0]["dataFilter"]["timeRange"]["from"][:10]
        requested.append((day, body["evalscript"].count("B03") > 0))
        left, bottom, right, top = body["input"]["bounds"]["bbox"]
        w, h = body["output"]["width"], body["output"]["height"]
        res = (right - left) / w
        cg = Grid(epsg=32645, transform=(res, 0.0, left, 0.0, -res, top), width=w, height=h)
        n_clear = int(round(clear_by_day[day] * w))
        scl = np.full((h, w), 9.0)
        scl[:, :n_clear] = 4
        if "B03" in body["evalscript"]:
            arr = np.stack([np.full((h, w), 0.1), np.full((h, w), 0.05), scl, np.ones((h, w))])
        else:
            arr = np.stack([scl, np.ones((h, w))])
        return _tiff_on(cg, arr), {}

    monkeypatch.setattr(sh, "get_token", lambda *a, **k: "T")
    monkeypatch.setattr(sh, "_http_post", fake_post)
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=40, height=30)
    arr, label = sh.fetch_s2_best(g, around, 5, CFG, after=EVENT, credentials=("a", "b"))
    assert arr.shape == (4, 30, 40) and "20260829" in label
    scl_days = [d for d, full in requested if not full]
    assert sorted(scl_days) == ["2026-08-27", "2026-08-29", "2026-08-31"]   # 08-24 is before the event
    assert [d for d, full in requested if full] == ["2026-08-29"]
    # the SCL probe runs at 20 m
    assert sh.coarse_grid(g, 20.0).width == 20 and sh.coarse_grid(g, 20.0).height == 15


def test_fetch_s2_best_none_without_candidates(monkeypatch):
    monkeypatch.setattr(sh, "search_items", lambda *a, **k: [])
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=40, height=30)
    assert sh.fetch_s2_best(g, datetime(2026, 8, 28, tzinfo=timezone.utc), 5, CFG, credentials=("a", "b")) is None


@pytest.mark.parametrize("flag, expected_after", [(True, EVENT), (False, None), ("absent", EVENT)])
def test_require_after_event_switch(tmp_path, monkeypatch, flag, expected_after):
    """s2.require_after_event (default true): only post-event S2 dates count as evidence (P1.6 review item)."""
    seen = {}
    monkeypatch.setattr(sh, "fetch_s2_best", lambda *a, **k: seen.update(after=k.get("after")) or None)
    ctx = make_ctx(tmp_path)
    if flag == "absent":
        ctx.cfg["s2"].pop("require_after_event", None)
    else:
        ctx.cfg["s2"]["require_after_event"] = flag
    s2mod.stage_s2(ctx)
    assert seen["after"] == expected_after


def test_default_config_requires_post_event_s2():
    assert CFG["s2"]["require_after_event"] is True


def test_switch_is_part_of_the_cache_key(tmp_path, monkeypatch):
    calls = []

    def fake(grid, around, days, cfg, **kw):
        calls.append(kw.get("after"))
        return bands(grid.height, grid.width, scl_value=6, b03=0.1, b11=0.02), "S2A"

    monkeypatch.setattr(sh, "fetch_s2_best", fake)
    ctx = make_ctx(tmp_path)
    s2mod.stage_s2(ctx)
    ctx.cfg["s2"]["require_after_event"] = False
    s2mod.stage_s2(ctx)
    assert calls == [EVENT, None]   # the second setting is fetched, not served from the first one's cache

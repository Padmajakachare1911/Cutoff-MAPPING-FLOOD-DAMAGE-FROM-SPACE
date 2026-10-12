"""P1.5 - Copernicus GLO-30 terrain stage: tiles, slope, HAND, D8, crop to the run grid."""
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from cutoff.contracts_check import validate_run_dir
from cutoff.data import dem as demmod
from cutoff.geo.grid import Grid, make_grid
from cutoff.geo.terrain import buffered_grid, crop_to, hand_flowdir, slope_degrees
from cutoff.runctx import RunContext

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))


def _grid(h, w, res=10.0):
    return Grid(epsg=32645, transform=(res, 0.0, 330000.0, 0.0, -res, 3115000.0), width=w, height=h)


def test_glo30_tile_names():
    urls = demmod.glo30_tiles((85.28, 27.95, 85.42, 28.29))
    names = sorted(u.rsplit("/", 1)[1] for u in urls)
    assert names == ["Copernicus_DSM_COG_10_N27_00_E085_00_DEM.tif", "Copernicus_DSM_COG_10_N28_00_E085_00_DEM.tif"]
    assert urls[0].startswith("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N2")
    assert demmod.glo30_tiles((85.1, 28.1, 85.2, 28.2)) == [
        "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N28_00_E085_00_DEM/"
        "Copernicus_DSM_COG_10_N28_00_E085_00_DEM.tif"]
    assert [u.rsplit("/", 1)[1] for u in demmod.glo30_tiles((-0.5, -0.5, -0.1, -0.1))] == [
        "Copernicus_DSM_COG_10_S01_00_W001_00_DEM.tif"]


def test_slope_of_10_percent_plane():
    rows, cols = np.mgrid[0:50, 0:50]
    dem = (0.1 * cols * 10.0).astype(np.float32)   # 10 % grade along x
    s = slope_degrees(dem, 10.0)
    assert s.dtype == np.float32
    assert np.allclose(s, np.degrees(np.arctan(0.1)), atol=1e-3) and abs(s.mean() - 5.71) < 0.01


def test_hand_v_valley():
    h, w, c0, s, t = 300, 201, 100, 0.2, 0.01
    rows, cols = np.mgrid[0:h, 0:w]
    dem = (1000 + s * np.abs(cols - c0) * 10.0 + t * (h - 1 - rows) * 10.0).astype(np.float32)
    hand, d8 = hand_flowdir(dem, _grid(h, w))
    assert hand.dtype == np.float32 and d8.dtype == np.uint8
    rr = slice(100, 290)
    assert np.allclose(hand[rr, c0], 0.0)
    # grows linearly with distance from the channel (pyflwdir's priority-flood D8 drains a hillslope cell
    # diagonally downstream, so the per-pixel rise is s*10 plus at most one down-valley step t*10)
    k = np.arange(0, 91)  # stay clear of the domain edge (pyflwdir seeds outlets there; the stage buffers 3 km)
    for side in (+1, -1):
        prof = hand[100:200, c0 + side * k]  # diagonal drainage meets the channel k rows downstream: stay inside
        for row in prof:
            slope_px, icpt = np.polyfit(k, row, 1)
            assert np.abs(np.polyval([slope_px, icpt], k) - row).max() < 0.01 and abs(icpt) < 0.01  # float32 DEM ~1200 m
            assert s * 10.0 - 1e-3 <= slope_px <= (s + t) * 10.0 + 1e-3


def _downstream_drop(dem, d8):
    """Elevation drop to the D8 downstream cell for every interior cell (NaN for pits/nodata)."""
    off = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
    drop = np.full(dem.shape, np.nan)
    for code, (dr, dc) in off.items():
        r, c = np.nonzero(d8 == code)
        ok = (r + dr >= 0) & (r + dr < dem.shape[0]) & (c + dc >= 0) & (c + dc < dem.shape[1])
        drop[r[ok], c[ok]] = dem[r[ok], c[ok]] - dem[r[ok] + dr, c[ok] + dc]
    return drop


def test_d8_of_tilted_plane_points_downhill():
    rows, cols = np.mgrid[0:40, 0:60]
    for dem in ((500 - 0.1 * cols * 10.0), (500 - 0.05 * rows * 10.0 - 0.02 * cols * 10.0)):
        dem = dem.astype(np.float32)
        _hand, d8 = hand_flowdir(dem, _grid(40, 60), stream_upa_km2=0.01)
        inner = d8[1:-1, 1:-1]
        assert np.isin(inner, [1, 2, 4, 8, 16, 32, 64, 128]).all()          # no pits inside a plane
        assert (_downstream_drop(dem, d8)[1:-1, 1:-1] > 0).all()            # every cell points downhill


def test_nan_dem_gives_nan_hand_and_nodata_d8():
    rows, cols = np.mgrid[0:40, 0:60]
    dem = (500 - 0.1 * cols * 10.0).astype(np.float32)
    dem[10:15, 10:15] = np.nan
    hand, d8 = hand_flowdir(dem, _grid(40, 60), stream_upa_km2=0.01)
    assert np.isnan(hand[10:15, 10:15]).all() and (d8[10:15, 10:15] == 247).all()


def test_buffered_grid_and_crop():
    g = make_grid((85.33, 28.15, 85.35, 28.17))
    bg, (r0, c0) = buffered_grid(g, 3000)
    assert (r0, c0) == (300, 300) and bg.width == g.width + 600 and bg.height == g.height + 600
    assert bg.transform[2] == g.transform[2] - 3000 and bg.transform[5] == g.transform[5] + 3000
    a = np.arange(bg.width * bg.height, dtype=np.float32).reshape(bg.height, bg.width)
    cropped = crop_to(a, bg, g)
    assert cropped.shape == (g.height, g.width) and cropped[0, 0] == a[300, 300]


def _ctx(tmp_path, mode="fast"):
    g = make_grid((85.33, 28.15, 85.35, 28.17))
    run = tmp_path / "run"
    run.mkdir()
    g.to_json(run / "grid.json")
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    return RunContext(run_dir=run, run_id="t", aoi_bbox=(85.33, 28.15, 85.35, 28.17),
                      event_datetime=datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc),
                      osm_snapshot="2026-07-27T00:00:00Z", mode=mode, cfg=cfg, grid=g)


def _fake_dem(grid, buffer_m=0):
    bg, _ = buffered_grid(grid, buffer_m)
    rows, cols = np.mgrid[0:bg.height, 0:bg.width]
    c0 = bg.width // 2
    dem = (1200 + 0.3 * np.abs(cols - c0) * 10.0 + 0.02 * (bg.height - rows) * 10.0).astype(np.float32)
    return dem, bg


def test_stage_terrain_writes_contract_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(demmod, "dem_on_grid", lambda g, buffer_m=0: calls.append(buffer_m) or _fake_dem(g, buffer_m))
    monkeypatch.setattr(demmod, "glo30_tiles", lambda bbox, source=None: ["tile-a"])
    ctx = _ctx(tmp_path)
    out = demmod.stage_terrain(ctx)
    assert calls == [3000.0]
    assert out == {"dem_tiles": ["tile-a"], "hand_stream_upa_km2": 1.0}
    validate_run_dir(ctx.run_dir, keys=["dem", "slope", "hand", "flwdir"])
    import rasterio
    with rasterio.open(ctx.path("dem")) as ds:
        dem = ds.read(1)
    full, bg = _fake_dem(ctx.grid, 3000)
    np.testing.assert_array_equal(dem, full[300:300 + ctx.grid.height, 300:300 + ctx.grid.width])
    with rasterio.open(ctx.path("hand")) as ds:
        hand = ds.read(1)
    assert np.nanmin(hand) == 0.0 and np.isfinite(hand).mean() > 0.99
    # cached mode reuses the DEM written to the cache, without fetching
    monkeypatch.setattr(demmod, "dem_on_grid", lambda *a, **k: pytest.fail("cached mode must not fetch"))
    (tmp_path / "again").mkdir()
    ctx2 = _ctx(tmp_path / "again", mode="cached")
    ctx2.cfg["run"]["cache_dir"] = ctx.cfg["run"]["cache_dir"]
    demmod.stage_terrain(ctx2)
    validate_run_dir(ctx2.run_dir, keys=["dem", "slope", "hand", "flwdir"])


def test_stage_terrain_cached_mode_without_cache_raises(tmp_path):
    from cutoff.data.s1_acquire import CacheMiss

    with pytest.raises(CacheMiss, match="cache"):
        demmod.stage_terrain(_ctx(tmp_path, mode="cached"))


@pytest.mark.network
def test_live_dem_on_small_grid():
    g = make_grid((85.33, 28.15, 85.35, 28.17))
    dem, bg = demmod.dem_on_grid(g)
    assert bg == g and dem.shape == (g.height, g.width) and np.isfinite(dem).all()
    assert 1000 < float(np.median(dem)) < 4000

"""P1.7 - full (SNAP) backend: graph content, gpt command, reprojection onto the run grid, stage wiring."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
import yaml

from cutoff.data import snap
from cutoff.data.cdse import scenes_from_items
from cutoff.geo.grid import Grid, make_grid

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
ITEMS = json.loads((ROOT / "tests" / "fixtures" / "stac_trishuli_s1.json").read_text(encoding="utf-8"))
POST_ID = "S1D_IW_GRDH_1SDV_20260828T122141_20260828T122206_004326_007FA4_C73B_COG"


def nodes(graph):
    root = ET.parse(graph).getroot()
    return {n.get("id"): n for n in root.findall("node")}


def param(n, name):
    return n.find("parameters").find(name).text


def test_graph_is_kuro_siwo_with_the_four_changes():
    text = snap.GRAPH.read_text(encoding="utf-8")
    assert "Orion-AI-Lab/KuroSiwo" in text and "grd_preprocessing.xml" in text
    ns = nodes(snap.GRAPH)
    chain, cur = [], "Write"
    while True:
        chain.append(cur)
        src = ns[cur].find("sources")
        refs = [s.get("refid") for s in src] if src is not None else []
        if not refs:
            break
        cur = refs[0]
    assert chain[::-1] == ["Read", "Apply-Orbit-File", "Subset", "ThermalNoiseRemoval", "Remove-GRD-Border-Noise",
                           "Calibration", "Speckle-Filter", "Terrain-Correction", "Write"]
    assert "Land-Sea-Mask" not in ns                                             # change 2
    assert param(ns["Subset"], "geoRegion") == "${geoRegion}"                    # change 1
    tc = ns["Terrain-Correction"]                                                # change 3
    assert param(tc, "demName") == "Copernicus 30m Global DEM"
    assert param(tc, "mapProjection") == "${mapProjection}"
    assert float(param(tc, "pixelSpacingInMeter")) == 10.0
    assert param(tc, "saveLocalIncidenceAngle") == "true"
    assert param(tc, "sourceBands") == "Sigma0_VV,Sigma0_VH"
    assert param(tc, "imgResamplingMethod") == "BILINEAR_INTERPOLATION"
    sf = ns["Speckle-Filter"]                                                    # change 4 (= Kuro Siwo)
    assert (param(sf, "filter"), param(sf, "windowSize"), param(sf, "targetWindowSizeStr"), param(sf, "sigmaStr")) == \
        ("Lee Sigma", "7x7", "3x3", "0.9")
    cal = ns["Calibration"]
    assert param(cal, "outputImageScaleInDb") == "false" and param(cal, "outputSigmaBand") == "true"
    assert param(ns["Read"], "file") == "${input}" and param(ns["Write"], "file") == "${output}"


def test_geo_region_is_grid_plus_1km():
    from shapely import wkt

    g = make_grid((85.33, 28.15, 85.35, 28.17))
    poly = wkt.loads(snap.geo_region_wkt(g, buffer_m=1000))
    w, s, e, n = g.bounds_wgs84()
    pw, ps, pe, pn = poly.bounds
    assert pw < w - 0.009 and pe > e + 0.009 and ps < s - 0.008 and pn > n + 0.008
    assert pw > w - 0.02 and pn < n + 0.02


def test_gpt_command():
    g = make_grid((85.33, 28.15, 85.35, 28.17))
    cmd = snap.gpt_command("gpt", Path("in.zip"), Path("out.tif"), g)
    assert cmd[0] == "gpt" and cmd[1] == str(snap.GRAPH)
    assert "-Pinput=in.zip" in cmd and "-Poutput=out.tif" in cmd and "-PmapProjection=EPSG:32645" in cmd
    assert any(c.startswith("-PgeoRegion=POLYGON") for c in cmd)


def _write_snap_like(path, grid_big, vv, vh, lia):
    import rasterio
    with rasterio.open(path, "w", driver="GTiff", width=grid_big.width, height=grid_big.height, count=3,
                       dtype="float32", crs=grid_big.crs, transform=grid_big.affine, nodata=0) as ds:
        ds.write(np.stack([vv, vh, lia]).astype(np.float32))


def test_reproject_snap_output_onto_grid(tmp_path):
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=50, height=40)
    big = Grid(epsg=32645, transform=(10.0, 0.0, 329500.0, 0.0, -10.0, 3115500.0), width=200, height=200)
    rows, cols = np.mgrid[0:200, 0:200]
    vv = (0.01 + 0.001 * cols).astype(np.float32)
    vh = np.full((200, 200), 0.01, np.float32)
    lia = np.full((200, 200), 35.0, np.float32)
    vv[:, :60] = 0          # SNAP no-data (0) inside the run grid's west part
    _write_snap_like(tmp_path / "snap.tif", big, vv, vh, lia)
    arr = snap.snap_to_grid(tmp_path / "snap.tif", g)
    assert arr.shape == (4, 40, 50) and arr.dtype == np.float32
    # grid col c <-> big col c + 50
    np.testing.assert_allclose(arr[0, :, 20], 0.01 + 0.001 * 70, rtol=1e-5)
    np.testing.assert_allclose(arr[2], 35.0)
    assert (arr[3][:, :9] == 0).all() and (arr[3][:, 11:] == 1).all()
    assert np.isnan(arr[0][arr[3] == 0]).all()


def test_fetch_snap_runs_download_gpt_and_reprojects(tmp_path, monkeypatch):
    scene = next(s for s in scenes_from_items(ITEMS, (85.28, 28.10, 85.42, 28.29)) if s.id == POST_ID)
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=50, height=40)
    big = Grid(epsg=32645, transform=(10.0, 0.0, 329500.0, 0.0, -10.0, 3115500.0), width=200, height=200)
    calls = {}

    def fake_download(sc, dest, cfg, log=None):
        calls["download"] = sc.product_uuid
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"zip")
        return dest

    def fake_run(cmd, **kw):
        calls["cmd"] = cmd
        out = Path(next(c for c in cmd if c.startswith("-Poutput=")).split("=", 1)[1])
        _write_snap_like(out, big, np.full((200, 200), 0.05), np.full((200, 200), 0.01), np.full((200, 200), 40.0))

        class R:
            returncode = 0
            stdout = stderr = ""
        return R()

    monkeypatch.setattr(snap, "download_product", fake_download)
    monkeypatch.setattr(snap.subprocess, "run", fake_run)
    monkeypatch.setattr(snap, "find_gpt", lambda: "gpt")
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    arr = snap.fetch_s1_scene_snap(scene, g, cfg)
    assert calls["download"] == "9e6c24a1-24ca-419f-bcec-db66791dcf19"
    assert "-PmapProjection=EPSG:32645" in calls["cmd"]
    assert arr.shape == (4, 40, 50) and np.allclose(arr[0], 0.05) and (arr[3] == 1).all()


def test_stage_full_mode_skips_local_lee_sigma(tmp_path, monkeypatch):
    from cutoff.contracts_check import validate_run_dir
    from cutoff.data import s1_acquire
    from cutoff.geo import speckle
    from cutoff.runctx import RunContext

    bbox = (85.33, 28.15, 85.35, 28.17)
    g = make_grid(bbox)
    run = tmp_path / "run"
    run.mkdir()
    g.to_json(run / "grid.json")
    cfg = yaml.safe_load(yaml.safe_dump(CFG))
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    ctx = RunContext(run_dir=run, run_id="full", aoi_bbox=bbox, event_datetime=datetime(2026, 8, 26, 2, 52,
                     tzinfo=timezone.utc), osm_snapshot="2026-07-27T00:00:00Z", mode="full", cfg=cfg, grid=g)
    rng = np.random.default_rng(0)
    fake = lambda scene, grid, c: np.stack([rng.gamma(4.4, 0.05 / 4.4, (grid.height, grid.width)),
                                            np.full((grid.height, grid.width), 0.01), np.full((grid.height, grid.width), 40.0),
                                            np.ones((grid.height, grid.width))]).astype(np.float32)
    monkeypatch.setitem(s1_acquire.BACKENDS, "snap", fake)
    monkeypatch.setattr(s1_acquire, "search_items", lambda *a, **k: ITEMS)
    monkeypatch.setattr(speckle, "lee_sigma", lambda *a, **k: pytest.fail("SNAP output is already Lee-Sigma filtered"))
    out = s1_acquire.stage_s1(ctx)
    assert out["s1_backend"] == "snap"
    validate_run_dir(run, keys=["s1_pre_mean", "s1_post", "lia", "shadow_layover"])
    assert any(p.name.endswith(".snap.tif") for p in (tmp_path / "cache" / "s1").rglob("*.tif"))


def test_backend_consistency_stats():
    rng = np.random.default_rng(1)
    a = rng.gamma(4.4, 0.08 / 4.4, (100, 100)).astype(np.float32)
    b = a * 10 ** (0.3 / 10)                        # +0.3 dB everywhere
    hand = np.full((100, 100), 150.0)
    hand[:50] = 5.0                                 # valley: not stable terrain
    slope = np.full((100, 100), 10.0)
    shadow = np.zeros((100, 100), np.uint8)
    st = snap.backend_consistency(np.stack([a, a]), np.stack([b, b]), hand, slope, shadow)
    assert st["n_stable_px"] == 5000
    assert st["VV"]["median_abs_ddb"] == pytest.approx(0.3, abs=1e-3) and st["VV"]["p90_abs_ddb"] == pytest.approx(0.3, abs=1e-3)


@pytest.mark.network
@pytest.mark.slow
def test_live_full_mode_trishuli_post(tmp_path):
    """Acceptance: the Trishuli post scene processed in full mode passes the validator (needs SNAP + CDSE login)."""
    try:
        snap.find_gpt()
        snap.cdse_token(CFG)
    except (snap.SnapNotFound, snap.MissingCDSELogin) as e:
        pytest.skip(str(e))
    from cutoff.contracts_check import validate_run_dir
    from cutoff.data import s1_acquire
    from cutoff.runctx import RunContext

    bbox = (85.28, 28.10, 85.42, 28.29)
    g = make_grid(bbox)
    run = tmp_path / "run"
    run.mkdir()
    g.to_json(run / "grid.json")
    ctx = RunContext(run_dir=run, run_id="full", aoi_bbox=bbox, event_datetime=datetime(2026, 8, 26, 2, 52,
                     tzinfo=timezone.utc), osm_snapshot="2026-07-27T00:00:00Z", mode="full", cfg=CFG, grid=g)
    s1_acquire.stage_s1(ctx)
    validate_run_dir(run, keys=["s1_pre_mean", "s1_post", "lia", "shadow_layover"])


# ---------------------------------------------------------------- gpt -h parameter check (P1.7 open [U] item)
def _fake_help(known: dict[str, list[str]]):
    """subprocess.run stand-in printing `gpt <op> -h`-style parameter options."""
    def run(cmd, **kw):
        op = cmd[1]
        lines = [f"Usage:\n  gpt {op} [options]\n\nParameter Options:"]
        lines += [f"  -P{p}=<string>    Some description. Default value is 'x'." for p in known.get(op, [])]

        class R:
            returncode = 0 if op in known else 1
            stdout = "\n".join(lines)
            stderr = "" if op in known else f"Error: Unknown operator {op}"
        return R()
    return run


def _graph_params():
    out = {}
    for n in ET.parse(snap.GRAPH).getroot().findall("node"):
        op = n.find("operator").text
        if op not in ("Read", "Write"):
            out[op] = [c.tag for c in n.find("parameters")]
    return out


def test_check_gpt_params_all_known():
    rep = snap.check_gpt_params(gpt="gpt", run=_fake_help(_graph_params()))
    assert rep["ok"] is True and set(rep["operators"]) == set(_graph_params())
    assert all(v["missing"] == [] for v in rep["operators"].values())


def test_check_gpt_params_reports_missing_and_unknown_operator():
    known = _graph_params()
    known["Terrain-Correction"] = [p for p in known["Terrain-Correction"] if p != "saveLocalIncidenceAngle"]
    known.pop("Remove-GRD-Border-Noise")
    rep = snap.check_gpt_params(gpt="gpt", run=_fake_help(known))
    assert rep["ok"] is False
    assert rep["operators"]["Terrain-Correction"]["missing"] == ["saveLocalIncidenceAngle"]
    assert rep["operators"]["Remove-GRD-Border-Noise"]["error"]


@pytest.mark.slow
def test_live_gpt_knows_every_graph_parameter():
    try:
        gpt = snap.find_gpt()
    except snap.SnapNotFound as e:
        pytest.skip(str(e))
    rep = snap.check_gpt_params(gpt=gpt)
    assert rep["ok"], rep

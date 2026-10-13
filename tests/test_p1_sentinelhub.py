"""P1.3 - Sentinel Hub Process API backend (fast mode). HTTP is mocked; the live test needs credentials."""
import io
import json
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
import yaml

from cutoff.data import sentinelhub as sh
from cutoff.data.cdse import parse_dt, scenes_from_items
from cutoff.geo.grid import Grid, make_grid

ROOT = Path(__file__).resolve().parents[1]
CFG = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
ITEMS = json.loads((ROOT / "tests" / "fixtures" / "stac_trishuli_s1.json").read_text(encoding="utf-8"))
POST_ID = "S1D_IW_GRDH_1SDV_20260828T122141_20260828T122206_004326_007FA4_C73B_COG"


@pytest.fixture(scope="module")
def post_scene():
    return next(s for s in scenes_from_items(ITEMS, (85.28, 28.10, 85.42, 28.29)) if s.id == POST_ID)


def test_chunks_cover_grid_exactly_once():
    g = Grid(epsg=32645, transform=(10.0, 0.0, 300000.0, 0.0, -10.0, 3120000.0), width=6001, height=2600)
    wins = sh.chunk_windows(g, max_px=2500)
    count = np.zeros((g.height, g.width), np.int8)
    for r, c, h, w in wins:
        assert 0 < h <= 2500 and 0 < w <= 2500
        count[r:r + h, c:c + w] += 1
    assert (count == 1).all()
    cg = sh.chunk_grid(g, wins[1])
    assert cg.transform[2] % 10 == 0 and cg.transform[5] % 10 == 0 and cg.epsg == g.epsg


def test_request_body(post_scene):
    g = make_grid((85.33, 28.15, 85.35, 28.17))
    body = sh.s1_request_body(post_scene, g, CFG)
    d = body["input"]["data"][0]
    tr = d["dataFilter"]["timeRange"]
    assert parse_dt(tr["from"]) == post_scene.start - timedelta(seconds=60)
    assert parse_dt(tr["to"]) == post_scene.end + timedelta(seconds=60)
    assert d["type"] == "sentinel-1-grd"
    assert d["dataFilter"]["orbitDirection"] == "ASCENDING"
    assert {"acquisitionMode": "IW", "polarization": "DV", "resolution": "HIGH"}.items() <= d["dataFilter"].items()
    assert d["processing"] == {"backCoeff": "SIGMA0_ELLIPSOID", "orthorectify": True,
                               "demInstance": "COPERNICUS_30", "speckleFilter": {"type": "NONE"}}
    b = body["input"]["bounds"]
    assert b["bbox"] == list(g.bounds)
    assert b["properties"]["crs"] == "http://www.opengis.net/def/crs/EPSG/0/32645"
    assert (body["output"]["width"], body["output"]["height"]) == (g.width, g.height)
    assert '"VV","VH","localIncidenceAngle","dataMask"' in body["evalscript"].replace(" ", "")
    assert 'sampleType:"FLOAT32"' in body["evalscript"].replace(" ", "")


def _tiff_on(grid: Grid, arr: np.ndarray) -> bytes:
    import rasterio
    from rasterio.io import MemoryFile

    with MemoryFile() as mf:
        with mf.open(driver="GTiff", width=grid.width, height=grid.height, count=arr.shape[0], dtype="float32",
                     crs=grid.crs, transform=grid.affine) as ds:
            ds.write(arr.astype(np.float32))
        return mf.read()


def test_mocked_fetch_places_chunks(monkeypatch, post_scene):
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=70, height=45)
    calls = []

    def fake_post(url, body, token):
        calls.append(body)
        left, bottom, right, top = body["input"]["bounds"]["bbox"]
        w, h = body["output"]["width"], body["output"]["height"]
        cg = Grid(epsg=32645, transform=(10.0, 0.0, left, 0.0, -10.0, top), width=w, height=h)
        rows, cols = np.mgrid[0:h, 0:w]
        r0, c0 = int(round((3115000.0 - top) / 10)), int(round((left - 330000.0) / 10))
        arr = np.stack([rows + r0, cols + c0, np.full((h, w), 38.0), np.ones((h, w))]).astype(np.float32)
        return _tiff_on(cg, arr), {"x-processingunits-spent": "0.5"}

    monkeypatch.setattr(sh, "get_token", lambda *a, **k: "TOKEN")
    monkeypatch.setattr(sh, "_http_post", fake_post)
    logs = []
    out = sh.fetch_s1_scene(post_scene, g, CFG, max_px=30, log=lambda **f: logs.append(f),
                            credentials=("id", "secret"))
    assert out.shape == (4, 45, 70) and out.dtype == np.float32
    rows, cols = np.mgrid[0:45, 0:70]
    np.testing.assert_array_equal(out[0], rows)
    np.testing.assert_array_equal(out[1], cols)
    assert len(calls) == len(sh.chunk_windows(g, 30)) == 6
    assert all(c["input"]["data"][0]["dataFilter"]["orbitDirection"] == "ASCENDING" for c in calls)
    assert [l["processing_units"] for l in logs] == [0.5] * 6


def test_mocked_fetch_rejects_off_grid_response(monkeypatch, post_scene):
    g = Grid(epsg=32645, transform=(10.0, 0.0, 330000.0, 0.0, -10.0, 3115000.0), width=20, height=20)
    shifted = Grid(epsg=32645, transform=(10.0, 0.0, 330005.0, 0.0, -10.0, 3115000.0), width=20, height=20)
    monkeypatch.setattr(sh, "get_token", lambda *a, **k: "TOKEN")
    monkeypatch.setattr(sh, "_http_post", lambda u, b, t: (_tiff_on(shifted, np.ones((4, 20, 20))), {}))
    with pytest.raises(ValueError, match="transform"):
        sh.fetch_s1_scene(post_scene, g, CFG, credentials=("id", "secret"))


def test_token_is_cached_until_expiry(monkeypatch):
    sh._TOKENS.clear()
    n = {"calls": 0}

    class Resp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            n["calls"] += 1
            return {"access_token": f"T{n['calls']}", "expires_in": 600}

    monkeypatch.setattr(sh.requests, "post", lambda *a, **k: Resp())
    assert sh.get_token("a", "b", "https://x/token") == "T1"
    assert sh.get_token("a", "b", "https://x/token") == "T1"
    sh._TOKENS[("a", "https://x/token")] = ("T1", 0.0)       # expired
    assert sh.get_token("a", "b", "https://x/token") == "T2"


def test_missing_credentials_raise_clear_error(monkeypatch, tmp_path):
    monkeypatch.delenv("SH_CLIENT_ID", raising=False)
    monkeypatch.delenv("SH_CLIENT_SECRET", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sh, "_ENV_FILES", [tmp_path / ".env"])
    with pytest.raises(sh.MissingCredentials, match="SH_CLIENT_ID"):
        sh.sh_credentials()


@pytest.mark.network
def test_live_trishuli_post_chunk(post_scene):
    """Trishuli post scene (85A, 08-28), one 5 x 5 km chunk."""
    import rasterio
    from rasterio.io import MemoryFile

    try:
        creds = sh.sh_credentials()
    except sh.MissingCredentials as e:
        pytest.skip(str(e))
    g = Grid(epsg=32645, transform=(10.0, 0.0, 333000.0, 0.0, -10.0, 3120000.0), width=500, height=500)
    body = sh.s1_request_body(post_scene, g, CFG)
    content, headers = sh._http_post(CFG["s1"]["sentinelhub"]["process_url"], body,
                                     sh.get_token(*creds, CFG["s1"]["sentinelhub"]["token_url"]))
    with MemoryFile(content) as mf, mf.open() as ds:
        assert np.allclose(tuple(ds.transform)[:6], g.transform, atol=1e-3)
        arr = ds.read()
    vv, lia, dm = arr[0], arr[2], arr[3] > 0
    assert dm.mean() > 0.5
    assert 0.01 <= float(np.median(vv[dm & (vv > 0)])) <= 0.3
    assert ((lia[dm] >= 0) & (lia[dm] <= 90)).mean() > 0.9


def test_rejected_login_reports_server_reason_without_secret(monkeypatch):
    sh._TOKENS.clear()

    class Resp:
        status_code = 401
        headers = {"content-type": "application/json"}

        def json(self):
            return {"error": "invalid_client", "error_description": "Invalid client or Invalid client credentials"}

    monkeypatch.setattr(sh.requests, "post", lambda *a, **k: Resp())
    with pytest.raises(sh.LoginRejected, match="invalid_client.*Invalid client credentials") as ei:
        sh.get_token("my-id", "TOP-SECRET", "https://x/token")
    assert "TOP-SECRET" not in str(ei.value)

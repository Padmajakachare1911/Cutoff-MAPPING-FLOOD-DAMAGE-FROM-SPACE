"""Sentinel Hub Process API on CDSE - the fast-mode S1 backend (Owner: P1, task P1.3; S2 fetch for P1.6).

Decision D1: sigma0 (SIGMA0_ELLIPSOID, no terrain flattening, like Kuro Siwo), orthorectified with
COPERNICUS_30, no server speckle filter (we apply geo/speckle.lee_sigma ourselves). The API has no
relative-orbit filter, so a scene is pinned by its exact acquisition window (+-60 s) and orbit direction.
A request is limited to 2500 x 2500 px, so the run grid is tiled into grid-aligned chunks.

Credentials: SH_CLIENT_ID / SH_CLIENT_SECRET (environment, or the git-ignored .env at the repo root).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

import numpy as np
import requests

from cutoff.data.cdse import Scene, iso, parse_dt, search_items
from cutoff.geo.grid import Grid

MAX_PX = 2500
TIME_PAD_S = 60
_TOKENS: dict[tuple[str, str], tuple[str, float]] = {}
_ENV_FILES = [Path.cwd() / ".env", Path(__file__).resolve().parents[3] / ".env"]

S1_EVALSCRIPT = (
    "//VERSION=3\n"
    'function setup(){return {input:[{bands:["VV","VH","localIncidenceAngle","dataMask"]}],'
    'output:{bands:4,sampleType:"FLOAT32"}};}\n'
    "function evaluatePixel(s){return [s.VV,s.VH,s.localIncidenceAngle,s.dataMask];}"
)


class MissingCredentials(RuntimeError):
    pass


def _read_env_files() -> dict[str, str]:
    vals: dict[str, str] = {}
    for p in _ENV_FILES:
        if Path(p).exists():
            for line in Path(p).read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    vals.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return vals


def env(name: str) -> str | None:
    return os.environ.get(name) or _read_env_files().get(name) or None


def sh_credentials() -> tuple[str, str]:
    cid, secret = env("SH_CLIENT_ID"), env("SH_CLIENT_SECRET")
    if not (cid and secret):
        raise MissingCredentials(
            "Sentinel Hub credentials missing: set SH_CLIENT_ID and SH_CLIENT_SECRET in .env (CDSE dashboard "
            "https://shapps.dataspace.copernicus.eu/dashboard -> User settings -> OAuth clients).")
    return cid, secret


def get_token(client_id, client_secret, token_url) -> str:            # cache until expiry
    key = (client_id, token_url)
    tok = _TOKENS.get(key)
    if tok and tok[1] > time.time():
        return tok[0]
    r = requests.post(token_url, data={"grant_type": "client_credentials", "client_id": client_id,
                                       "client_secret": client_secret}, timeout=60)
    r.raise_for_status()
    d = r.json()
    _TOKENS[key] = (d["access_token"], time.time() + float(d.get("expires_in", 300)) - 60.0)
    return d["access_token"]


# --------------------------------------------------------------------------- tiling
def chunk_windows(grid: Grid, max_px: int = MAX_PX) -> list[tuple[int, int, int, int]]:
    """(row_off, col_off, height, width) windows of at most max_px x max_px that tile the grid exactly once."""
    def splits(n):
        k = -(-n // max_px)
        edges = [round(i * n / k) for i in range(k + 1)]
        return [(edges[i], edges[i + 1] - edges[i]) for i in range(k)]
    return [(r, c, h, w) for r, h in splits(grid.height) for c, w in splits(grid.width)]


def chunk_grid(grid: Grid, win: tuple[int, int, int, int]) -> Grid:
    r, c, h, w = win
    a = grid.affine
    return Grid(epsg=grid.epsg, transform=(a.a, 0.0, a.c + c * a.a, 0.0, a.e, a.f + r * a.e), width=w, height=h)


def _bounds_block(grid: Grid) -> dict:
    return {"bbox": list(grid.bounds),
            "properties": {"crs": f"http://www.opengis.net/def/crs/EPSG/0/{grid.epsg}"}}


def _output_block(grid: Grid) -> dict:
    return {"width": grid.width, "height": grid.height,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]}


def s1_request_body(scene: Scene, chunk: Grid, cfg: dict) -> dict:
    """Process API request for one chunk (bbox = chunk bounds in grid CRS metres)."""
    shc = cfg["s1"]["sentinelhub"]
    pad = timedelta(seconds=TIME_PAD_S)
    return {
        "input": {"bounds": _bounds_block(chunk),
                  "data": [{"type": "sentinel-1-grd",
                            "dataFilter": {"timeRange": {"from": iso(scene.start - pad), "to": iso(scene.end + pad)},
                                           "acquisitionMode": "IW", "polarization": "DV", "resolution": "HIGH",
                                           "orbitDirection": scene.direction.upper()},
                            "processing": {"backCoeff": shc.get("back_coeff", "SIGMA0_ELLIPSOID"),
                                           "orthorectify": bool(shc.get("orthorectify", True)),
                                           "demInstance": shc.get("dem_instance", "COPERNICUS_30"),
                                           "speckleFilter": {"type": shc.get("speckle_filter", "NONE")}}}]},
        "output": _output_block(chunk),
        "evalscript": S1_EVALSCRIPT,
    }


def _http_post(url: str, body: dict, token: str, retries: int = 4) -> tuple[bytes, dict]:
    """POST a Process API request; returns (TIFF bytes, response headers). Retries 429 / 5xx."""
    for attempt in range(retries + 1):
        r = requests.post(url, json=body, headers={"Authorization": f"Bearer {token}", "Accept": "image/tiff"},
                          timeout=300)
        if r.status_code == 200:
            return r.content, dict(r.headers)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
            time.sleep(float(r.headers.get("Retry-After", 2 ** (attempt + 1))))
            continue
        raise RuntimeError(f"Sentinel Hub {r.status_code}: {r.text[:500]}")
    raise RuntimeError("unreachable")


def _read_tiff_on(content: bytes, chunk: Grid, bands: int) -> np.ndarray:
    from rasterio.io import MemoryFile

    with MemoryFile(content) as mf, mf.open() as ds:
        if not np.allclose(tuple(ds.transform)[:6], chunk.transform, atol=1e-3):
            raise ValueError(f"Sentinel Hub response transform {tuple(ds.transform)[:6]} != chunk grid "
                             f"{chunk.transform}")
        if (ds.width, ds.height, ds.count) != (chunk.width, chunk.height, bands):
            raise ValueError(f"Sentinel Hub response {(ds.count, ds.height, ds.width)} != "
                             f"{(bands, chunk.height, chunk.width)}")
        return ds.read().astype(np.float32)


def _fetch_tiled(grid: Grid, bands: int, body_for: Callable[[Grid], dict], cfg: dict, max_px: int,
                 log: Callable | None, credentials, what: str) -> np.ndarray:
    shc = cfg["s1"]["sentinelhub"]
    cid, secret = credentials or sh_credentials()
    out = np.full((bands, grid.height, grid.width), np.nan, np.float32)
    for win in chunk_windows(grid, max_px):
        chunk = chunk_grid(grid, win)
        t0 = time.time()
        content, headers = _http_post(shc["process_url"], body_for(chunk), get_token(cid, secret, shc["token_url"]))
        r, c, h, w = win
        out[:, r:r + h, c:c + w] = _read_tiff_on(content, chunk, bands)
        pu = {k.lower(): v for k, v in headers.items()}.get("x-processingunits-spent")
        if log:
            log(event="sentinelhub_request", what=what, window=list(win),
                processing_units=float(pu) if pu is not None else None, seconds=round(time.time() - t0, 2))
    return out


def fetch_s1_scene(scene: Scene, grid: Grid, cfg, max_px: int = MAX_PX, log: Callable | None = None,
                   credentials: tuple[str, str] | None = None) -> np.ndarray:
    """(4, H, W) float32 on the grid: VV, VH (linear sigma0), LIA (deg), dataMask (0/1)."""
    return _fetch_tiled(grid, 4, lambda ch: s1_request_body(scene, ch, cfg), cfg, max_px, log, credentials,
                        scene.id)


# --------------------------------------------------------------------------- Sentinel-2 (P1.6)
S2_EVALSCRIPT = (
    "//VERSION=3\n"
    'function setup(){return {input:[{bands:["B03","B11","SCL","dataMask"]}],'
    'output:{bands:4,sampleType:"FLOAT32"}};}\n'
    "function evaluatePixel(s){return [s.B03,s.B11,s.SCL,s.dataMask];}"
)
S2_SCL_EVALSCRIPT = (
    "//VERSION=3\n"
    'function setup(){return {input:[{bands:["SCL","dataMask"]}],output:{bands:2,sampleType:"UINT8"}};}\n'
    "function evaluatePixel(s){return [s.SCL,s.dataMask];}"
)


def s2_request_body(day_from: datetime, day_to: datetime, chunk: Grid, evalscript: str) -> dict:
    return {
        "input": {"bounds": _bounds_block(chunk),
                  "data": [{"type": "sentinel-2-l2a",
                            "dataFilter": {"timeRange": {"from": iso(day_from), "to": iso(day_to)},
                                           "mosaickingOrder": "leastCC"}}]},
        "output": _output_block(chunk),
        "evalscript": evalscript,
    }


def coarse_grid(grid: Grid, res: float) -> Grid:
    """Same origin and extent (rounded up) at a coarser resolution, e.g. 20 m for the cheap SCL probe."""
    a = grid.affine
    f = res / a.a
    return Grid(epsg=grid.epsg, transform=(res, 0.0, a.c, 0.0, -res, a.f),
                width=int(np.ceil(grid.width / f)), height=int(np.ceil(grid.height / f)))


def fetch_s2_best(grid, around: datetime, days: int, cfg, after: datetime | None = None, max_px: int = MAX_PX,
                  log: Callable | None = None, credentials: tuple[str, str] | None = None
                  ) -> tuple[np.ndarray, str] | None:
    """Best Sentinel-2 L2A date within +-days of `around` (and strictly after `after`, the event), by the
    number of clear AOI pixels in a cheap 20 m SCL probe. Returns ((4, H, W) float32 B03, B11 reflectance,
    SCL, dataMask on the grid; the chosen date's item ids joined by ","), or None without candidates."""
    s2 = cfg.get("s2", {})
    clear_scl = np.asarray(s2.get("clear_scl", [4, 5, 6, 7]))
    lo, hi = around - timedelta(days=days), around + timedelta(days=days)
    if after is not None:
        lo = max(lo, after + timedelta(seconds=1))
    if lo >= hi:
        return None
    items = search_items(grid.bounds_wgs84(), lo, hi, cfg["s1"]["stac_url"], collection=s2.get("collection",
                                                                                                "sentinel-2-l2a"))
    by_day: dict[str, list[dict]] = {}
    for it in items:
        dt = parse_dt(it["properties"]["datetime"])
        if lo <= dt <= hi:
            by_day.setdefault(dt.date().isoformat(), []).append(it)
    if not by_day:
        return None
    creds = credentials or sh_credentials()

    def window(day: str) -> tuple[datetime, datetime]:
        d0 = datetime.fromisoformat(day).replace(tzinfo=around.tzinfo)
        return max(d0, lo), min(d0 + timedelta(days=1), hi)

    probe = coarse_grid(grid, 20.0)
    scores = []
    for day in sorted(by_day):
        f, t = window(day)
        arr = _fetch_tiled(probe, 2, lambda ch: s2_request_body(f, t, ch, S2_SCL_EVALSCRIPT), cfg, max_px, log,
                           creds, f"S2 SCL {day}")
        n_clear = int((np.isin(arr[0], clear_scl) & (arr[1] > 0)).sum())
        gap = abs((datetime.fromisoformat(day).replace(tzinfo=around.tzinfo) - around).total_seconds())
        scores.append((-n_clear, gap, day))
        if log:
            log(event="s2_probe", day=day, clear_px_20m=n_clear, of=probe.width * probe.height)
    _, _, best = min(scores)
    f, t = window(best)
    arr = _fetch_tiled(grid, 4, lambda ch: s2_request_body(f, t, ch, S2_EVALSCRIPT), cfg, max_px, log, creds,
                       f"S2 {best}")
    return arr, ",".join(sorted(it["id"] for it in by_day[best]))

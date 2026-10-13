"""Full-mode (ESA SNAP) S1 backend - the reference / compliance path (Owner: P1, task P1.7).

graphs/s1_cutoff.xml is the Kuro Siwo GRD graph with four changes (see its header): subset to the grid + 1 km,
no Land-Sea-Mask, Terrain-Correction with the Copernicus 30 m DEM in the grid's UTM CRS at 10 m with the local
incidence angle saved, Lee Sigma 7x7 / 3x3 / 0.9 as in Kuro Siwo. The product zip is downloaded from the CDSE
OData service (Bearer token from the CDSE login), `gpt` runs the graph, and the output is reprojected
(bilinear) onto the run grid. Lee Sigma comes from SNAP here, so stage_s1 skips geo/speckle.lee_sigma.

Needs: SNAP `gpt` (env SNAP_GPT, PATH, or the default install folder) and CDSE_USERNAME / CDSE_PASSWORD.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import numpy as np
import requests

from cutoff.data.cdse import Scene
from cutoff.geo.grid import Grid

GRAPH = Path(__file__).resolve().parents[3] / "graphs" / "s1_cutoff.xml"
ODATA_URL = "https://download.dataspace.copernicus.eu/odata/v1/Products({uuid})/$value"
CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
_GPT_CANDIDATES = [Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "esa-snap" / "bin" / "gpt.exe",
                   Path.home() / "esa-snap" / "bin" / "gpt", Path("/opt/esa-snap/bin/gpt"),
                   Path("/usr/local/esa-snap/bin/gpt")]


class SnapNotFound(RuntimeError):
    pass


class MissingCDSELogin(RuntimeError):
    pass


def find_gpt() -> str:
    exe = os.environ.get("SNAP_GPT") or shutil.which("gpt")
    if exe:
        return exe
    for p in _GPT_CANDIDATES:
        if p.exists():
            return str(p)
    raise SnapNotFound("ESA SNAP `gpt` not found: install SNAP (https://step.esa.int) or set SNAP_GPT")


def cdse_token(cfg: dict | None = None) -> str:
    """Access token for the CDSE download service (password grant, public client `cdse-public`)."""
    from cutoff.data.sentinelhub import env

    user, pwd = env("CDSE_USERNAME"), env("CDSE_PASSWORD")
    if not (user and pwd):
        raise MissingCDSELogin("CDSE login missing: set CDSE_USERNAME and CDSE_PASSWORD in .env")
    url = ((cfg or {}).get("s1", {}).get("sentinelhub", {}).get("token_url")) or CDSE_TOKEN_URL
    r = requests.post(url, data={"grant_type": "password", "client_id": "cdse-public", "username": user,
                                 "password": pwd}, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def download_product(scene: Scene, dest: Path, cfg: dict, log: Callable | None = None) -> Path:
    """Stream the product zip from CDSE OData to `dest` (skipped if it already exists)."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    if not scene.product_uuid:
        raise ValueError(f"{scene.id}: no product uuid in the STAC item (properties._private.product_uuid)")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    t0 = time.time()
    url = ODATA_URL.format(uuid=scene.product_uuid)
    with requests.get(url, headers={"Authorization": f"Bearer {cdse_token(cfg)}"}, stream=True, timeout=600) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=8 << 20):
                f.write(chunk)
    tmp.replace(dest)
    if log:
        log(event="snap_download", scene=scene.id, bytes=dest.stat().st_size, seconds=round(time.time() - t0, 1))
    return dest


def geo_region_wkt(grid: Grid, buffer_m: float = 1000.0) -> str:
    """WKT polygon (WGS84) of the grid bounds + buffer_m, for the Subset node."""
    from pyproj import Transformer

    left, bottom, right, top = grid.bounds
    left, bottom, right, top = left - buffer_m, bottom - buffer_m, right + buffer_m, top + buffer_m
    t = Transformer.from_crs(grid.epsg, 4326, always_xy=True)
    n = 10
    xs = [left + (right - left) * i / n for i in range(n + 1)]
    ys = [bottom + (top - bottom) * i / n for i in range(n + 1)]
    ring_x = xs + [right] * (n + 1) + xs[::-1] + [left] * (n + 1)
    ring_y = [bottom] * (n + 1) + ys + [top] * (n + 1) + ys[::-1]
    lon, lat = t.transform(ring_x, ring_y)
    w, s, e, nn = min(lon), min(lat), max(lon), max(lat)
    return f"POLYGON(({w:.6f} {s:.6f}, {e:.6f} {s:.6f}, {e:.6f} {nn:.6f}, {w:.6f} {nn:.6f}, {w:.6f} {s:.6f}))"


def gpt_command(gpt: str, product: Path, out_tif: Path, grid: Grid) -> list[str]:
    return [gpt, str(GRAPH), f"-Pinput={product}", f"-Poutput={out_tif}",
            f"-PgeoRegion={geo_region_wkt(grid, 1000.0)}", f"-PmapProjection=EPSG:{grid.epsg}"]


def snap_to_grid(snap_tif: Path, grid: Grid) -> np.ndarray:
    """SNAP GeoTIFF (bands Sigma0_VV, Sigma0_VH, localIncidenceAngle; 0 = no data) -> (4, H, W) float32 on
    the run grid: VV, VH linear sigma0, LIA deg, dataMask (bilinear)."""
    import rasterio
    from rasterio.warp import Resampling, reproject

    out = np.full((3, grid.height, grid.width), np.nan, np.float32)
    with rasterio.open(snap_tif) as ds:
        if ds.count < 3:
            raise ValueError(f"{snap_tif}: expected 3 bands (Sigma0_VV, Sigma0_VH, localIncidenceAngle), got {ds.count}")
        for i in range(3):
            src = ds.read(i + 1).astype(np.float32)
            src[src == 0] = np.nan
            reproject(src, out[i], src_transform=ds.transform, src_crs=ds.crs, src_nodata=np.nan,
                      dst_transform=grid.affine, dst_crs=grid.crs, dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
    dm = (np.isfinite(out[0]) & np.isfinite(out[1]) & (out[0] > 0) & (out[1] > 0)).astype(np.float32)
    return np.concatenate([out, dm[None]]).astype(np.float32)


def fetch_s1_scene_snap(scene: Scene, grid: Grid, cfg, log: Callable | None = None) -> np.ndarray:
    """(4, H, W) float32: VV, VH (linear sigma0, Lee-Sigma filtered by SNAP), LIA, dataMask on the grid."""
    from cutoff.data.s1_acquire import grid_hash

    gpt = find_gpt()
    cache = Path(cfg.get("run", {}).get("cache_dir", "cache/")) / "s1"
    product = download_product(scene, cache / "products" / f"{scene.id}.zip", cfg, log=log)
    out_tif = cache / "snap" / f"{scene.id}_{grid_hash(grid)}.tif"
    if not out_tif.exists():
        out_tif.parent.mkdir(parents=True, exist_ok=True)
        cmd = gpt_command(gpt, product, out_tif, grid)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not out_tif.exists():
            raise RuntimeError(f"gpt failed ({r.returncode}): {(r.stderr or r.stdout)[-2000:]}")
        if log:
            log(event="snap_gpt", scene=scene.id, seconds=round(time.time() - t0, 1))
    return snap_to_grid(out_tif, grid)


# --------------------------------------------------------------------------- E3c helper
def backend_consistency(a_lin, b_lin, hand, slope, shadow, hand_min: float = 100.0, slope_max: float = 20.0) -> dict:
    """|delta dB| between two backends' (2, H, W) linear VV/VH over stable terrain
    (HAND > hand_min, slope < slope_max, no shadow/layover, valid in both)."""
    from cutoff.geo.sar import to_db

    a, b = to_db(a_lin), to_db(b_lin)
    stable = (np.asarray(hand) > hand_min) & (np.asarray(slope) < slope_max) & (np.asarray(shadow) == 0)
    out = {"n_stable_px": int(stable.sum()), "hand_min_m": hand_min, "slope_max_deg": slope_max}
    for i, pol in enumerate(("VV", "VH")):
        d = np.abs(a[i] - b[i])[stable & np.isfinite(a[i]) & np.isfinite(b[i])]
        out[pol] = {"n_px": int(d.size),
                    "median_abs_ddb": float(np.median(d)) if d.size else None,
                    "p90_abs_ddb": float(np.percentile(d, 90)) if d.size else None}
    return out

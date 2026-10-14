"""Stage `terrain`: Copernicus GLO-30 -> dem, slope, HAND, D8 flow directions on the run grid.

Owner: P1 (task P1.5). GLO-30 COGs are read from the public AWS bucket (no auth) over /vsicurl/,
mosaicked and resampled bilinearly onto a 3 km-buffered copy of the run grid. HAND and D8 are
computed there (streams = upstream area > 1 km^2) and cropped; slope is np.gradient on dem.tif.
The buffered DEM is cached under <cache_dir>/dem/<grid_hash>.tif so `cached` mode needs no network.

Limitation (report): GLO-30 is a surface model (trees and buildings included) and at 30 m it smooths
narrow gorges, which inflates HAND near the riverbank - hence the 60 m HAND corridor in `rules`.
"""
from __future__ import annotations

import hashlib
import math
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from cutoff.data.s1_acquire import _tmp_path
from cutoff.geo.grid import Grid
from cutoff.geo.terrain import buffered_grid, crop_to, hand_flowdir, slope_degrees
from cutoff.runctx import RunContext

GLO30_SOURCE = "https://copernicus-dem-30m.s3.amazonaws.com"
_GDAL_ENV = {"GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR", "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
             "GDAL_HTTP_MAX_RETRY": "4", "GDAL_HTTP_RETRY_DELAY": "2"}


def _tile_name(lat: int, lon: int) -> str:
    ns = f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}"
    ew = f"{'E' if lon >= 0 else 'W'}{abs(lon):03d}"
    return f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"


def glo30_tiles(bbox_wgs84, source: str | None = None) -> list[str]:
    """URLs of the 1 x 1 degree GLO-30 tiles intersecting bbox (W, S, E, N); a tile is named after its
    lower-left corner."""
    w, s, e, n = bbox_wgs84
    src = (source or GLO30_SOURCE).rstrip("/")
    urls = []
    span = lambda lo, hi: range(math.floor(lo), max(math.ceil(hi), math.floor(lo) + 1))
    for lat in span(s, n):
        for lon in span(w, e):
            name = _tile_name(lat, lon)
            urls.append(f"{src}/{name}/{name}.tif")
    return urls


def _local_tiles(urls: list[str], directory: Path) -> list[Path]:
    """Cache whole public COGs for large mosaics, avoiding thousands of range requests."""
    import rasterio
    import requests

    directory.mkdir(parents=True, exist_ok=True)

    def download(url: str) -> Path | None:
        identity = hashlib.sha256(url.encode()).hexdigest()[:12]
        path = directory / f"{identity}_{url.rsplit('/', 1)[-1]}"
        if path.is_file():
            return path
        tmp = _tmp_path(path)
        # An interrupted earlier process may have retained a raw prefix of this
        # immutable GLO-30 COG. Resume only this URL's namespaced file.
        prefixes = list(directory.glob(f"{path.name}.*.tmp"))
        prefix = max(prefixes, key=lambda p: p.stat().st_size, default=None)
        if prefix is not None and prefix != tmp:
            shutil.copyfile(prefix, tmp)
        for attempt in range(3):
            offset = tmp.stat().st_size if tmp.is_file() else 0
            try:
                headers = {"Range": f"bytes={offset}-"} if offset else {}
                with requests.get(url, headers=headers, stream=True, timeout=(20, 60)) as response:
                    if response.status_code == 404:
                        tmp.unlink(missing_ok=True)
                        return None  # ocean tiles are absent from GLO-30
                    response.raise_for_status()
                    resumed = offset > 0 and response.status_code == 206
                    if resumed and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise RuntimeError("Copernicus DEM resume returned an unexpected byte range")
                    size = 0
                    with tmp.open("ab" if resumed else "wb") as output:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            output.write(chunk)
                            size += len(chunk)
                    expected = response.headers.get("Content-Length")
                    if expected and size != int(expected):
                        raise RuntimeError("Incomplete Copernicus DEM tile download")
                with rasterio.open(tmp) as raster:
                    if raster.crs is None or raster.count != 1:
                        raise ValueError("Invalid Copernicus DEM tile")
                tmp.replace(path)
                return path
            except requests.RequestException:
                if attempt == 2:
                    raise  # retain the prefix for a later retry
                time.sleep(attempt + 1)
            except Exception:
                tmp.unlink(missing_ok=True)
                raise
        raise RuntimeError("Copernicus DEM tile download did not complete")

    with ThreadPoolExecutor(max_workers=9) as pool:
        return [path for path in pool.map(download, urls) if path is not None]


def dem_on_grid(grid: Grid, buffer_m: float = 0, *, tile_cache: Path | None = None) -> tuple[np.ndarray, Grid]:
    """GLO-30 heights (float32, NaN no-data) bilinearly resampled onto `grid` buffered by buffer_m,
    and that (buffered) grid."""
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import Resampling, reproject

    bg, _ = buffered_grid(grid, buffer_m) if buffer_m else (grid, (0, 0))
    w, s, e, n = bg.bounds_wgs84()
    pad = 2.0 / 3600.0  # two GLO-30 pixels around the envelope for the bilinear kernel
    window = (w - pad, s - pad, e + pad, n + pad)
    out = np.full((bg.height, bg.width), np.nan, np.float32)
    with rasterio.Env(**_GDAL_ENV):
        srcs = []
        urls = glo30_tiles(window)
        locations = _local_tiles(urls, tile_cache) if tile_cache is not None else [f"/vsicurl/{url}" for url in urls]
        for location in locations:
            try:
                srcs.append(rasterio.open(location))
            except rasterio.errors.RasterioIOError:
                continue  # tile absent (open ocean)
        if not srcs:
            raise RuntimeError(f"no GLO-30 tile found for {window}")
        try:
            mosaic, mtrans = merge(srcs, bounds=window, nodata=np.nan, dtype="float32")
            reproject(mosaic[0], out, src_transform=mtrans, src_crs=srcs[0].crs, src_nodata=np.nan,
                      dst_transform=bg.affine, dst_crs=bg.crs, dst_nodata=np.nan, resampling=Resampling.bilinear)
        finally:
            for ds in srcs:
                ds.close()
    return out, bg


def _cached_dem(ctx: RunContext, buffer_m: float) -> tuple[np.ndarray, Grid]:
    import rasterio

    from cutoff.data.s1_acquire import CacheMiss, cache_root, grid_hash

    bg, _ = buffered_grid(ctx.grid, buffer_m)
    path = cache_root(ctx) / "dem" / f"{grid_hash(bg)}.tif"
    if path.exists():
        with rasterio.open(path) as ds:
            return ds.read(1).astype(np.float32), bg
    if ctx.mode == "cached":
        raise CacheMiss(f"cached mode: no DEM in the cache ({path}); run scripts/cache_aoi.py for this AOI first")
    if bg.width * bg.height >= 10_000_000:
        ctx.log("terrain", event="large_dem_download", tiles_dir=str(cache_root(ctx) / "dem/tiles"))
        dem, bg2 = dem_on_grid(ctx.grid, buffer_m=buffer_m, tile_cache=cache_root(ctx) / "dem/tiles")
    else:
        dem, bg2 = dem_on_grid(ctx.grid, buffer_m=buffer_m)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_path(path)
    with rasterio.open(tmp, "w", **bg2.profile("float32", 1, np.nan)) as dst:
        dst.write(dem[None])
    tmp.replace(path)
    return dem, bg2


def stage_terrain(ctx: RunContext) -> dict:
    """Writes: dem.tif, slope.tif, hand.tif, flwdir_d8.tif.

    Returns: {"dem_tiles": [str, ...], "hand_stream_upa_km2": float}
    """
    from cutoff.geo import raster_io

    dcfg = ctx.cfg.get("dem", {})
    buffer_m = float(dcfg.get("hand_buffer_m", 3000))
    upa = float(dcfg.get("stream_upa_km2", 1.0))
    bdem, bg = _cached_dem(ctx, buffer_m)
    tiles = glo30_tiles(bg.bounds_wgs84(), dcfg.get("source"))
    hand_b, d8_b = hand_flowdir(bdem, bg, stream_upa_km2=upa)
    dem = crop_to(bdem, bg, ctx.grid)
    hand = crop_to(hand_b, bg, ctx.grid)
    d8 = crop_to(d8_b, bg, ctx.grid)
    slope = slope_degrees(dem, abs(ctx.grid.affine.a))
    raster_io.write(ctx, "dem", dem, tags={"source": "Copernicus GLO-30", "resampling": "bilinear"})
    raster_io.write(ctx, "slope", slope)
    raster_io.write(ctx, "hand", hand, tags={"stream_upa_km2": upa, "buffer_m": buffer_m})
    raster_io.write(ctx, "flwdir", d8, tags={"codes": "pyflwdir d8"})
    ctx.log("terrain", dem_tiles=tiles, buffer_m=buffer_m, hand_stream_upa_km2=upa,
            dem_valid_fraction=round(float(np.isfinite(dem).mean()), 4),
            hand_valid_fraction=round(float(np.isfinite(hand).mean()), 4))
    return {"dem_tiles": tiles, "hand_stream_upa_km2": upa}

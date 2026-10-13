"""Terrain derivatives on the analysis grid (Owner: P1, task P1.5): slope, HAND, D8 flow directions.

HAND and D8 come from pyflwdir (streams = upstream area > 1 km^2). They are computed on a DEM buffered
by >= 3 km around the run grid (same 10 m alignment), then cropped back, so that rivers entering the AOI
and drainage leaving it are represented.
"""
from __future__ import annotations

import numpy as np

from cutoff.geo.grid import Grid

DEM_NODATA = -9999.0


def slope_degrees(dem, pixel_m) -> np.ndarray:
    """Slope in degrees from np.gradient (central differences) at pixel_m spacing. NaN stays NaN."""
    gy, gx = np.gradient(np.asarray(dem, dtype=np.float64), float(pixel_m))
    return np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)


def hand_flowdir(dem, grid: Grid, stream_upa_km2: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """(hand_m float32 NaN-nodata, d8 uint8 pyflwdir codes with 247 = nodata) for a DEM on `grid`."""
    import pyflwdir

    z = np.asarray(dem, dtype=np.float32)
    valid = np.isfinite(z)
    data = np.where(valid, z, DEM_NODATA).astype(np.float32)
    flw = pyflwdir.from_dem(data=data, nodata=DEM_NODATA, transform=grid.affine, latlon=False)
    upa = flw.upstream_area(unit="km2")
    drain = upa > stream_upa_km2
    hand = flw.hand(drain=drain, elevtn=data).astype(np.float32)
    hand[(hand == DEM_NODATA) | ~valid] = np.nan
    d8 = flw.to_array("d8").astype(np.uint8)
    d8[~valid] = 247
    return hand, d8


def buffered_grid(grid: Grid, buffer_m: float) -> tuple[Grid, tuple[int, int]]:
    """Grid extended by buffer_m on every side (whole pixels, same alignment) and the (row, col) offset
    of the original grid inside it."""
    a = grid.affine
    n = int(round(buffer_m / a.a))
    bg = Grid(epsg=grid.epsg, transform=(a.a, 0.0, a.c - n * a.a, 0.0, a.e, a.f - n * a.e),
              width=grid.width + 2 * n, height=grid.height + 2 * n)
    return bg, (n, n)


def crop_to(arr: np.ndarray, src: Grid, dst: Grid) -> np.ndarray:
    """Crop an array on `src` to the (contained, same-alignment) grid `dst`."""
    sa, da = src.affine, dst.affine
    c0 = int(round((da.c - sa.c) / sa.a))
    r0 = int(round((da.f - sa.f) / sa.e))
    if c0 < 0 or r0 < 0 or c0 + dst.width > src.width or r0 + dst.height > src.height:
        raise ValueError("destination grid is not contained in the source grid")
    return arr[..., r0:r0 + dst.height, c0:c0 + dst.width]

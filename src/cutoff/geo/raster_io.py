"""Read/write contract rasters of a run folder on the run grid (shared helper, created by P2).

`read(ctx, key)` returns (bands, H, W) or (H, W) for single-band rasters; float rasters keep NaN.
`write(ctx, key, arr)` uses the contract dtype / band count / nodata from contracts.RASTERS and the
run grid profile, so stage code cannot write an off-grid or wrong-dtype raster by accident.
"""
from __future__ import annotations

import numpy as np

from cutoff.contracts import RASTERS


def read(ctx, key: str, squeeze: bool = True) -> np.ndarray:
    import rasterio

    with rasterio.open(ctx.path(key)) as ds:
        arr = ds.read()
    return arr[0] if squeeze and arr.shape[0] == 1 else arr


def write(ctx, key: str, arr: np.ndarray, tags: dict | None = None) -> None:
    import rasterio

    _name, bands, dtype, nodata, _owner = RASTERS[key]
    arr = np.asarray(arr)
    arr = arr[None] if arr.ndim == 2 else arr
    if arr.shape != (bands, ctx.grid.height, ctx.grid.width):
        raise ValueError(f"{key}: shape {arr.shape} != {(bands, ctx.grid.height, ctx.grid.width)}")
    nd = float("nan") if nodata == "nan" else nodata
    with rasterio.open(ctx.path(key), "w", **ctx.grid.profile(dtype, bands, nd)) as dst:
        dst.write(arr.astype(dtype))
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})

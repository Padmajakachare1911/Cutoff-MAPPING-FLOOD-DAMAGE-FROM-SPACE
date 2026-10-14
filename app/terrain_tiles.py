"""MapLibre terrain tiles made only from the run's Copernicus DEM."""
import io
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.transform import from_bounds
from rasterio.warp import Resampling, reproject


@lru_cache(maxsize=256)
def terrain_png(path: Path, z: int, x: int, y: int) -> bytes:
    if not 0 <= z <= 18 or not (0 <= x < 2**z and 0 <= y < 2**z):
        raise ValueError("Invalid terrain tile coordinates")
    half = 20037508.342789244
    span = 2 * half / 2**z
    west, north = -half + x * span, half - y * span
    tile = np.full((256, 256), np.nan, np.float32)
    with rasterio.open(path) as source:
        reproject(rasterio.band(source, 1), tile, src_transform=source.transform, src_crs=source.crs,
                  src_nodata=source.nodata, dst_transform=from_bounds(west, north-span, west+span, north, 256, 256),
                  dst_crs="EPSG:3857", dst_nodata=np.nan, resampling=Resampling.bilinear)
    # Mapbox Terrain-RGB: elevation = -10000 + encoded * 0.1 metres.
    value = np.round((np.nan_to_num(tile, nan=0.0) + 10000) * 10).clip(0, 16777215).astype(np.uint32)
    rgb = np.stack([(value >> 16) & 255, (value >> 8) & 255, value & 255], axis=-1).astype(np.uint8)
    out = io.BytesIO()
    Image.fromarray(rgb).save(out, format="PNG")
    return out.getvalue()

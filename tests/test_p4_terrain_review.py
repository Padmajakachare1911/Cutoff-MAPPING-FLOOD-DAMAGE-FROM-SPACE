"""Real geographic failure cases: absent heights and misleading RGB encoding."""
import importlib.util
import io
import re
from pathlib import Path

import numpy as np
from PIL import Image
import pytest
import rasterio
from rasterio.transform import from_bounds


def module():
    path = Path(__file__).parents[1] / "app/terrain_tiles.py"
    spec = importlib.util.spec_from_file_location("review_tiles", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_display_mesh_fits_pinned_renderers_uint16_index_buffer():
    # Native MapLibre mesh = (cells+1)^2 surface vertices plus six rows of
    # skirt vertices. Overflow produces diagonal triangles across the map.
    source = (Path(__file__).parents[1] / "app/static/terrain-map.js").read_text(encoding="utf-8")
    cells = int(re.search(r"renderer\.meshSize=(\d+)", source).group(1))
    vertices = (cells + 1) ** 2 + 6 * (cells + 1)
    assert cells >= 128
    assert vertices <= 65536, "Terrain indices wrap and corrupt the rendered surface"


def test_partial_coverage_is_unavailable_instead_of_a_zero_height_cliff(tmp_path):
    path = tmp_path / "dem.tif"
    half = 20037508.342789244
    # z=1,x=1,y=0 spans the whole NE quarter; only a tiny piece exists.
    with rasterio.open(path, "w", driver="GTiff", width=8, height=8,
                       count=1, dtype="float32", crs=3857,
                       transform=from_bounds(0, half-10000, 10000, half, 8, 8)) as ds:
        ds.write(np.full((8,8), 1800, "float32"), 1)
    with pytest.raises(ValueError, match="outside observed"):
        module().terrain_png(path, 1, 1, 0, 512, strict=True)


def test_512_tile_preserves_metres_without_exaggeration(tmp_path):
    path = tmp_path / "dem.tif"
    half = 20037508.342789244
    with rasterio.open(path, "w", driver="GTiff", width=32, height=32,
                       count=1, dtype="float32", crs=3857,
                       transform=from_bounds(-half,-half,half,half,32,32)) as ds:
        ds.write(np.full((32,32), 1234.5, "float32"), 1)
    pixels = np.asarray(Image.open(io.BytesIO(module().terrain_png(path,1,1,0,512,strict=True))))
    code = pixels.astype("uint32")
    heights = -10000 + .1*(code[...,0]*65536+code[...,1]*256+code[...,2])
    assert pixels.shape == (512,512,3)
    assert np.allclose(heights, 1234.5, atol=.05)

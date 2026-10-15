"""Guard scientific meanings and dated observations in display-only maps."""
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from map_layers import raster_overlay
from prepare_display import selection_window
import context_tiles


def raster(tmp_path, values, nodata=None):
    array = np.asarray(values)
    if array.ndim == 2:
        array = array[None]
    path = tmp_path / 'evidence.tif'
    with rasterio.open(path, 'w', driver='GTiff', width=array.shape[2], height=array.shape[1],
                       count=len(array), dtype=array.dtype, crs='EPSG:3857',
                       transform=from_origin(300000, 300000, 10, 10), nodata=nodata) as out:
        out.write(array)
    return path


def test_flood_map_never_colors_disturbance_or_permanent_water_as_flood(tmp_path):
    path = raster(tmp_path, np.tile(np.array([0, 1, 2, 3, 4, 5, 254], dtype='uint8'), (8, 1)), 254)
    flood, _ = raster_overlay(path, 'flood')
    changes, _ = raster_overlay(path, 'changes')
    permanent, _ = raster_overlay(path, 'permanent')
    assert np.all(flood[:, [1, 2], 3] > 0)
    assert not flood[:, [0, 3, 4, 5, 6], 3].any()
    assert np.all(changes[:, [3, 4], 3] > 0)
    assert not changes[:, [0, 1, 2, 5, 6], 3].any()
    assert np.all(permanent[:, 5, 3] > 0)
    assert not permanent[:, [0, 1, 2, 3, 4, 6], 3].any()


def test_no_observation_hatch_survives_class_254_nodata(tmp_path):
    path = raster(tmp_path, np.full((12, 12), 254, dtype='uint8'), 254)
    image, _ = raster_overlay(path, 'no_obs')
    assert np.any(image[..., 3] > 0) and np.any(image[..., 3] == 0)


def test_rgb_uses_actual_reflectance_with_one_fixed_stretch_and_data_mask(tmp_path):
    values = np.ones((6, 8, 8), dtype='float32')
    values[0], values[1], values[2] = 0, .15, .3
    values[5, 0, 0] = 0
    image, _ = raster_overlay(raster(tmp_path, values, np.nan), 'rgb')
    assert np.array_equal(image[4, 4, [0, 2, 3]], [0, 255, 255])
    assert 165 < image[4, 4, 1] < 185
    assert image[0, 0, 3] == 0


def test_probability_is_monotonic_blue_without_opaque_low_scores(tmp_path):
    image, _ = raster_overlay(raster(tmp_path, np.tile(np.array([0, .5, 1], dtype='float32'), (8, 1))), 'score')
    assert np.array_equal(image[4, :, 3], [0, 115, 230])


def test_same_day_optical_mosaics_cannot_cross_the_event():
    event = datetime(2026, 8, 26, 2, 52, tzinfo=UTC)
    start, end = selection_window('2026-08-26', event, 'before')
    assert start < end < event
    start, end = selection_window('2026-08-26', event, 'after')
    assert event < start < end


def test_compressed_rgb_transport_preserves_black_pixels_and_transparency(tmp_path):
    values = np.full((4, 8, 8), 255, dtype='uint8')
    values[0] = 0
    values[3, 0, 0] = 0
    image, _ = raster_overlay(raster(tmp_path, values), 'rgb')
    assert np.array_equal(image[4, 4], [0, 255, 255, 255])
    assert image[0, 0, 3] == 0


def test_historical_context_uses_local_cache_without_a_network_call(tmp_path, monkeypatch):
    target = tmp_path / 'display_context/s2cloudless-2025/12/2504/1693.jpg'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'cached tile fixture')
    def no_network(*args, **kwargs):
        raise AssertionError('A cached tile must not request the network')
    monkeypatch.setattr(context_tiles.requests, 'get', no_network)
    assert context_tiles.historical_tile(tmp_path, 12, 2504, 1693) == b'cached tile fixture'

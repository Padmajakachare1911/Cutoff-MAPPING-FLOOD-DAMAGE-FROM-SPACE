"""Display rasters and pre-event vectors without calculating reported statistics."""
from __future__ import annotations

import html
import math
from pathlib import Path

import folium
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import (
    Resampling,
    calculate_default_transform,
    reproject,
    transform_bounds,
)

from cutoff.contracts import HAZARD_CLASS_NAMES, ODBL_NOTICE

COLORS = {0: '#ffffff', 1: '#0879bd', 2: '#80c8e7', 3: '#cf930c', 4: '#b23b27', 5: '#394e99', 254: '#727d85'}
STATUS_COLORS = {'connected': '#26876b', 'degraded': '#d48a08', 'cut_off': '#b82929', 'unknown': '#64748b'}


def raster_overlay(path, kind, band=1, max_size=1400):
    """Warp to Web Mercator before PNG display; lat/lon bounds locate the Mercator image."""
    with rasterio.open(path) as source:
        trans, width, height = calculate_default_transform(source.crs, 'EPSG:3857', source.width,
                                                          source.height, *source.bounds)
        scale = min(1, max_size / max(width, height))
        width, height = max(1, round(width * scale)), max(1, round(height * scale))
        bounds = transform_bounds(source.crs, 'EPSG:3857', *source.bounds)
        trans = from_bounds(*bounds, width, height)
        data = np.full((height, width), np.nan, dtype='float32')
        categorical = kind in {'hazard', 'no_obs', 's2'}
        reproject(rasterio.band(source, band), data, src_transform=source.transform, src_crs=source.crs,
                  src_nodata=source.nodata, dst_transform=trans, dst_crs='EPSG:3857', dst_nodata=np.nan,
                  resampling=Resampling.nearest if categorical else Resampling.bilinear)
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    valid = np.isfinite(data)
    if kind == 'hazard':
        for code, color in COLORS.items():
            if code in (0, 254):
                continue
            selected = data == code
            rgba[selected, :3] = tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
            rgba[selected, 3] = 170
    elif kind == 'no_obs':
        rows, cols = np.indices(data.shape)
        selected = (data == 254) & ((rows + cols) % 9 < 3)
        rgba[selected] = (65, 72, 80, 220)
    elif kind == 's2':
        rgba[data == 1] = (37, 181, 179, 180)
    elif kind == 'score':
        clipped = np.clip(np.nan_to_num(data), 0, 1)
        rgba[..., 0] = (clipped * 255).astype(np.uint8)
        rgba[..., 1] = ((1-clipped) * 130).astype(np.uint8)
        rgba[..., 2] = ((1-clipped) * 200).astype(np.uint8)
        rgba[valid, 3] = 170
    else:
        with np.errstate(divide='ignore', invalid='ignore'):
            db = np.clip(10*np.log10(np.where(data > 0, data, np.nan)), -30, 5)
        gray = np.nan_to_num((db + 30) / 35 * 255).astype(np.uint8)
        rgba[..., :3] = gray[..., None]
        rgba[np.isfinite(db), 3] = 255
    west, south, east, north = transform_bounds('EPSG:3857', 'EPSG:4326', *bounds)
    return rgba, [[south, west], [north, east]]


def vector_data(path):
    frame = gpd.read_file(path).to_crs(4326)
    for column in frame.columns:
        if column == 'geometry':
            continue
        if column in {'t0_min', 't1_min'}:
            frame[column] = frame[column].map(lambda v: 'unreachable' if isinstance(v, (float, int)) and math.isinf(v)
                                            else 'unknown' if v is None or (isinstance(v, float) and math.isnan(v))
                                            else str(v))
        elif frame[column].dtype == object:
            frame[column] = frame[column].map(lambda v: html.escape(str(v)) if v is not None else '')
    data = frame.__geo_interface__
    data['attribution'] = ODBL_NOTICE
    return data


def build_map(results, root, scenario):
    root = Path(root)
    west, south, east, north = results.inputs.aoi_bbox
    # No contemporary basemap: all mapped infrastructure is from the pre-event run.
    map_ = folium.Map(location=[(south+north)/2, (west+east)/2], tiles=None, zoom_start=12,
                      control_scale=True, prefer_canvas=True)
    map_.fit_bounds([[south, west], [north, east]])
    for filename, kind, label, band, shown in [
        ('s1_pre_mean.tif', 'gray', 'Pre-event VV dB', 1, False),
        ('s1_post.tif', 'gray', 'Post-event VV dB', 1, False),
        ('p_model.tif', 'score', 'Model score (calibrated on global floods)', 3, False),
        ('s2_water.tif', 's2', 'Sentinel-2 clear-sky water evidence', 1, False),
        ('hazard_class.tif', 'hazard', 'Hazard evidence tiers', 1, True),
        ('hazard_class.tif', 'no_obs', 'No observation (hatched)', 1, True),
    ]:
        path = root / filename
        if path.is_file():
            rgba, bounds = raster_overlay(path, kind, band=band)
            folium.raster_layers.ImageOverlay(rgba, bounds=bounds, name=label, show=shown,
                                              mercator_project=False).add_to(map_)
    for filename, label, color in [
        ('osm_roads.gpkg', 'Pre-event mapped roads', '#7c8795'),
        ('exposure_buildings.gpkg', 'Exposed buildings', '#a62f38'),
        ('exposure_roads.gpkg', 'Exposed roads', '#d77314'),
        ('flowpath.gpkg', 'Downstream flow path', '#119878'),
    ]:
        path = root / filename
        if path.is_file():
            data = vector_data(path)
            if data['features']:
                folium.GeoJson(data, name=label, show=filename != 'osm_roads.gpkg',
                               style_function=lambda feature, color=color: {'color': color, 'weight': 2,
                                                                           'fillOpacity': 0.4}).add_to(map_)
    path = root / f'roads_status_{scenario}.gpkg'
    if path.is_file():
        data = vector_data(path)
        data['features'] = [feature for feature in data['features'] if feature['properties']['closed']]
        if data['features']:
            folium.GeoJson(data, name=f'Closed roads - {scenario}',
                           style_function=lambda feature: {'color': '#c42828', 'weight': 4}).add_to(map_)
    path = root / f'settlements_{scenario}.gpkg'
    if path.is_file():
        data = vector_data(path)
        if data['features']:
            fields = ['name', 'status', 't0_min', 't1_min']
            if 'trail_access' in data['features'][0]['properties']:
                fields.append('trail_access')
            folium.GeoJson(data, name=f'Settlements - {scenario}',
                marker=folium.CircleMarker(radius=6, fill=True, fill_opacity=0.9),
                style_function=lambda feature: {'color': STATUS_COLORS[feature['properties']['status']],
                                                'fillColor': STATUS_COLORS[feature['properties']['status']]},
                popup=folium.GeoJsonPopup(fields=fields, labels=True)).add_to(map_)
    legend = '<div style="position:fixed;bottom:20px;left:20px;z-index:9999;background:white;padding:12px;' \
             'border:1px solid #ccc;font:12px sans-serif"><b>Hazard evidence</b><br>'
    for code, color in COLORS.items():
        if code:
            legend += f'<span style="color:{color}">■</span> {HAZARD_CLASS_NAMES[code].replace("_", " ")}<br>'
    legend += 'Hatched: no observation<br>Score layer: 0 (blue) → 1 (red)</div>'
    map_.get_root().html.add_child(folium.Element(legend))
    folium.LayerControl(collapsed=False).add_to(map_)
    return map_

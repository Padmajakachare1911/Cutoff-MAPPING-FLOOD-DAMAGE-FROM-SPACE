"""Acquire dated, display-only Sentinel-2 context and pre-event OSM rivers.

No analysis raster, checkpoint, threshold or reported statistic is modified.
Run: python app/prepare_display.py <run directory> [<run directory> ...]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import geopandas as gpd
import httpx
import numpy as np
import rasterio
import requests
import yaml
from shapely.geometry import box, mapping

from cutoff.cli import load_dotenv
from cutoff.data.cdse import parse_dt
from cutoff.data.osm import assert_pre_event
from cutoff.data.sentinelhub import (
    S2_SCL_EVALSCRIPT, _fetch_tiled, coarse_grid, s2_request_body, sh_credentials,
    chunk_windows, chunk_grid, get_token,
)
from cutoff.geo.grid import make_grid

ROOT = Path(__file__).resolve().parents[1]
RGB_SCRIPT = '''//VERSION=3
function setup(){return {input:[{bands:["B04","B03","B02","dataMask"]}],
output:{bands:4,sampleType:"UINT8"}};}
function stretch(x){return 255*Math.pow(Math.max(0,Math.min(1,x/0.30)),1/1.8);}
function evaluatePixel(s){return [stretch(s.B04),stretch(s.B03),stretch(s.B02),255*s.dataMask];}'''


def fetch_rgb(grid, start, end, cfg, creds, log):
    """PNG transport avoids downloading huge uncompressed display-only TIFFs."""
    from PIL import Image
    settings = cfg['s1']['sentinelhub']
    output = np.zeros((4, grid.height, grid.width), dtype='uint8')
    for row, col, height, width in chunk_windows(grid, 1500):
        chunk = chunk_grid(grid, (row, col, height, width))
        body = s2_request_body(start, end, chunk, RGB_SCRIPT)
        body['output']['responses'][0]['format']['type'] = 'image/png'
        token = get_token(*creds, settings['token_url'])
        for attempt in range(3):
            response = requests.post(settings['process_url'], json=body,
                headers={'Authorization':'Bearer '+token, 'Accept':'image/png'}, timeout=90)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(5*(attempt+1))
                continue
            response.raise_for_status()
            break
        rgba = np.asarray(Image.open(io.BytesIO(response.content)).convert('RGBA'))
        if rgba.shape != (height, width, 4):
            raise ValueError('Optical PNG dimensions do not match requested grid')
        output[:,row:row+height,col:col+width] = np.moveaxis(rgba,-1,0)
        log(event='display_rgb_tile', date=start.date().isoformat(), window=[row,col,height,width], bytes=len(response.content))
    return output


def catalogue_items(grid, lo, hi, folder):
    cache = folder / 'before_catalogue.json'
    if cache.exists():
        return json.loads(cache.read_text(encoding='utf-8'))
    query = {'collections':['sentinel-2-l2a'], 'bbox':list(grid.bounds_wgs84()),
             'datetime':lo.isoformat()+'/'+hi.isoformat(), 'limit':100}
    for attempt in range(3):
        response = requests.post('https://stac.dataspace.copernicus.eu/v1/search', json=query, timeout=60)
        if response.status_code == 429 and attempt < 2:
            time.sleep(15)
            continue
        response.raise_for_status()
        body = response.json()
        if any(link.get('rel') == 'next' for link in body.get('links', [])):
            raise ValueError('Display search needs a narrower acquisition window')
        items = body.get('features', [])
        cache.write_text(json.dumps(items), encoding='utf-8')
        return items
    return []


def selection_window(day, event, phase):
    """Never let a calendar-day mosaic cross the event boundary."""
    start = parse_dt(day + 'T00:00:00Z')
    end = start + timedelta(days=1)
    if phase == 'before':
        end = min(end, event - timedelta(seconds=1))
    else:
        start = max(start, event + timedelta(seconds=1))
    if start >= end:
        raise ValueError('Optical observation is on the wrong side of the event')
    return start, end


def write_tif(path, array, grid):
    temp = path.with_suffix('.tmp.tif')
    with rasterio.open(temp, 'w', **grid.profile('float32', array.shape[0], np.nan)) as out:
        out.write(array.astype('float32'))
    temp.replace(path)


def prepare(root):
    load_dotenv(ROOT / '.env')
    cfg = yaml.safe_load((ROOT / 'configs/default.yaml').read_text())
    result = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    inputs = result['inputs']
    event = parse_dt(inputs['event_datetime'])
    assert_pre_event(inputs['osm_snapshot'], event)
    folder = root / 'display'
    folder.mkdir(exist_ok=True)
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'version': 1, 'display_only': True, 'observations': {}, 'warnings': [],
        'event_datetime': inputs['event_datetime'], 'osm_snapshot': inputs['osm_snapshot'],
        'attribution': 'Contains modified Copernicus Sentinel data; © OpenStreetMap contributors, ODbL.',
    }
    grid = make_grid(tuple(inputs['aoi_bbox']), res=10, buffer_m=2000)
    creds = sh_credentials()

    def log(**fields):
        print(root.name, json.dumps(fields), flush=True)

    def save_manifest():
        temp = manifest_path.with_suffix('.tmp.json')
        temp.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        temp.replace(manifest_path)

    for phase in ('before', 'after'):
        if phase in manifest['observations'] and (folder / f'{phase}_rgb.tif').exists():
            continue
        try:
            if phase == 'before':
                lo, hi = event - timedelta(days=35), event - timedelta(seconds=1)
            else:
                # Keep the already selected optical evidence date whenever possible.
                scenes = inputs.get('s2_scenes', [])
                if scenes:
                    stamp = scenes[0].split('_')[2][:8]
                    day = f'{stamp[:4]}-{stamp[4:6]}-{stamp[6:]}'
                    lo, hi = selection_window(day, event, phase)
                else:
                    lo, hi = event + timedelta(seconds=1), event + timedelta(days=12)
            if phase == 'after' and inputs.get('s2_scenes'):
                items = [{'id': scene, 'properties':{'datetime':lo.isoformat()}} for scene in inputs['s2_scenes']]
            else:
                items = catalogue_items(grid, lo, hi, folder)
            by_day = {}
            for item in items:
                dt = parse_dt(item['properties']['datetime'])
                if lo <= dt <= hi:
                    by_day.setdefault(dt.date().isoformat(), []).append(item)
            if not by_day:
                raise ValueError('No dated Sentinel-2 scenes available')
            # A cheap local probe avoids selecting by tile-wide cloudiness alone.
            candidates = sorted(by_day, key=lambda d: (min(i['properties'].get('eo:cloud_cover', 100) for i in by_day[d]), -parse_dt(d+'T00:00:00Z').timestamp()))[:4]
            probe = coarse_grid(grid, 60)
            scores, probes = [], {}
            for day in candidates:
                start, end = selection_window(day, event, phase)
                arr = _fetch_tiled(probe, 2, lambda g: s2_request_body(start, end, g, S2_SCL_EVALSCRIPT), cfg, 2500, log, creds, 'Display cloud probe '+day)
                clear = np.isin(arr[0], [4, 5, 6, 7]) & (arr[1] > 0)
                scores.append((-int(clear.sum()), abs((event-parse_dt(day+'T00:00:00Z')).total_seconds()), day))
                probes[day] = arr
            day = min(scores)[2]
            start, end = selection_window(day, event, phase)
            arr = fetch_rgb(grid, start, end, cfg, creds, log)
            temp = folder / f'{phase}_rgb.tmp.tif'
            with rasterio.open(temp, 'w', **grid.profile('uint8',4)) as out:
                out.write(arr)
            temp.replace(folder / f'{phase}_rgb.tif')
            scl = probes[day]
            clear = np.isin(scl[0], [4, 5, 6, 7]) & (scl[1] > 0)
            water = (scl[0] == 6) & clear
            water_layer = np.where(scl[1] > 0, water.astype('float32'), np.nan)[None]
            write_tif(folder / f'{phase}_water.tif', water_layer, probe)
            write_tif(folder / f'{phase}_scl.tif', scl[:1], probe)
            manifest['observations'][phase] = {
                'date': day, 'sensor': 'Sentinel-2 L2A', 'resolution_m': 10,
                'clear_fraction_context': round(float(clear.mean()), 4),
                'scene_ids': sorted(i['id'] for i in by_day[day]),
                'bands': ['B04', 'B03', 'B02', 'dataMask'],
                'rgb_stretch': 'Shared fixed reflectance 0–0.30, gamma 1/1.8; clouds retained.',
                'water_method': 'SCL=6 water at 60 m, dataMask>0. Display context, not flood classification. Original analysis S2 MNDWI layer retained separately at 10 m.',
                'request_window': [start.isoformat(), end.isoformat()],
            }
            manifest['warnings'] = [warning for warning in manifest['warnings'] if not warning.startswith(phase+' optical context unavailable')]
            save_manifest()
        except Exception as exc:
            # Preserve usable observations and expose the absence without inventing context.
            message = f'{phase} optical context unavailable: {type(exc).__name__}: {exc}'
            if message not in manifest['warnings']:
                manifest['warnings'].append(message)
            log(warning=message)
            save_manifest()
    water_path = folder / 'osm_water.gpkg'
    if not water_path.exists():
        try:
            query = {'aoi': mapping(box(*grid.bounds_wgs84())), 'filter': 'waterway=* or natural=water or water=*', 'time': inputs['osm_snapshot'], 'clip': True}
            response = httpx.post(cfg['osm']['api_v2']+'/extraction/features.parquet', json=query,
                                  headers={'authorization': os.environ.get('OHSOME_API_KEY', '')}, timeout=240)
            response.raise_for_status()
            raw = gpd.read_parquet(io.BytesIO(response.content), to_pandas_kwargs={'maps_as_pydicts':'strict'})
            raw = raw.to_crs(4326)
            tags = raw['tags'].map(lambda t: dict(t) if t is not None else {})
            clean = gpd.GeoDataFrame({'name': tags.map(lambda t: t.get('name:en') or t.get('name') or ''),
                                     'waterway': tags.map(lambda t: t.get('waterway') or t.get('water') or 'water')}, geometry=raw.geometry, crs=4326)
            clean.to_file(water_path, driver='GPKG')
            manifest['river_context'] = {'source':'Pre-event OpenStreetMap via ohsome v2', 'snapshot':inputs['osm_snapshot'], 'features':len(clean)}
            save_manifest()
        except Exception as exc:
            message = f'Pre-event river context unavailable: {type(exc).__name__}'
            if message not in manifest['warnings']:
                manifest['warnings'].append(message)
            log(warning=message)
            save_manifest()
    if not (root / 'flowpath.gpkg').exists() and water_path.exists():
        try:
            prepare_local_flow(root, water_path, manifest)
            save_manifest()
        except (ValueError, OSError) as exc:
            log(warning='Local downstream DEM trace unavailable: '+str(exc))
    log(event='display_ready', observations=list(manifest['observations']))


def prepare_local_flow(root, water_path, manifest):
    """A local D8 trace, never a flood wave or an invented valley axis."""
    from affine import Affine
    from cutoff.geo.flowpath import flowpath_from_dem
    from cutoff.geo.grid import Grid
    from rasterio.enums import Resampling
    path = root / 'display/flowpath.gpkg'
    if path.exists():
        return
    with rasterio.open(root / 'dem.tif') as source:
        height, width = max(1, source.height//3), max(1, source.width//3)
        dem = source.read(1, out_shape=(height, width), masked=True, resampling=Resampling.bilinear).filled(np.nan)
        affine = source.transform * Affine.scale(source.width/width, source.height/height)
        grid = Grid(source.crs.to_epsg(), tuple(affine)[:6], width, height)
    rivers = gpd.read_file(water_path).to_crs(grid.crs)
    rivers = rivers.loc[rivers.waterway.eq('river')].explode(index_parts=False)
    lines = [geometry.intersection(box(*grid.bounds)) for geometry in rivers.geometry if geometry.geom_type == 'LineString']
    lines = [line for line in lines if line.geom_type == 'LineString' and line.length > 100]
    if not lines:
        raise ValueError('No mapped river intersects the local DEM')
    river = max(lines, key=lambda line:line.length)
    candidates = []
    for x, y in [river.coords[0], river.coords[-1]]:
        row, col = rasterio.transform.rowcol(affine, x, y)
        row, col = min(height-1,max(0,row)), min(width-1,max(0,col))
        if np.isfinite(dem[row,col]):
            candidates.append((float(dem[row,col]), x, y))
    if not candidates:
        raise ValueError('Mapped river endpoints have no DEM observation')
    elevation, x, y = max(candidates)
    line = flowpath_from_dem(dem, grid, x, y, max_length_m=50000)
    frame = gpd.GeoDataFrame({'name':['Local downstream DEM trace'], 'length_km':[line.length/1000],
                             'display_only':[True]}, geometry=[line], crs=grid.crs)
    frame.to_file(path, driver='GPKG')
    manifest['local_flow'] = {'length_km':round(line.length/1000,3), 'method':'Copernicus GLO-30 DEM, resampled to ~30 m, D8 downstream; source is higher endpoint of longest dated OSM river inside DEM.',
                              'coverage':'Local DEM footprint only; not a flood propagation simulation or arrival-time forecast.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path, nargs='+')
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(prepare, [root.resolve() for root in args.runs]))

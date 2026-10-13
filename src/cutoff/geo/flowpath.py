"""Trace a downstream path from Copernicus DEM and list nearby pre-event OSM places."""
from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pyflwdir
from rasterio.transform import rowcol, xy
from shapely.geometry import LineString

from cutoff.data.osm import assert_pre_event, fetch_layer
from cutoff.geo.grid import Grid, make_grid
from cutoff.runctx import RunContext

STAGE = "flowpath"


def flowpath_from_dem(dem: np.ndarray, grid: Grid, start_x: float, start_y: float,
                      stream_upa_km2: float = 1.0, max_length_m: float = 150_000) -> LineString:
    """Build D8 flow, snap to the nearest stream cell, and trace downstream."""
    data = np.where(np.isfinite(dem), dem, -9999.0).astype(np.float32)
    flow = pyflwdir.from_dem(data=data, nodata=-9999.0, transform=grid.affine, latlon=False)
    upstream = flow.upstream_area("km2")
    candidates = np.argwhere((upstream > stream_upa_km2) & np.isfinite(dem))
    if not len(candidates):
        candidates = np.argwhere(np.isfinite(dem))
    if not len(candidates):
        raise ValueError("DEM contains no valid cells")
    start_row, start_col = rowcol(grid.affine, start_x, start_y)
    nearest = candidates[np.argmin((candidates[:, 0] - start_row) ** 2 + (candidates[:, 1] - start_col) ** 2)]
    start_idx = int(nearest[0] * grid.width + nearest[1])
    try:
        paths, _ = flow.path(idxs=np.array([start_idx]), direction="down", max_length=max_length_m, unit="m")
        indices = paths[0]
    except Exception:  # noqa: BLE001 - pyflwdir/affine version fallback, same D8 links
        indices, current, distance, seen = [], start_idx, 0.0, set()
        while current >= 0 and current not in seen and distance <= max_length_m:
            seen.add(current)
            indices.append(current)
            nxt = int(flow.idxs_ds[current])
            if nxt == current or nxt < 0:
                break
            r0, c0, r1, c1 = current // grid.width, current % grid.width, nxt // grid.width, nxt % grid.width
            distance += abs(grid.affine.a) * math.hypot(r1 - r0, c1 - c0)
            current = nxt
        indices = np.asarray(indices)
    if len(indices) < 2:
        raise ValueError("downstream trace did not leave its starting cell")
    rows, cols = np.divmod(indices, grid.width)
    xs, ys = xy(grid.affine, rows, cols)
    return LineString(zip(xs, ys))


def trace_flowpath(ctx: RunContext, lon: float, lat: float) -> dict:
    """Fetch a 30 m DEM around the source, write flowpath.gpkg, and return its summary."""
    from pyproj import Transformer

    from cutoff.data.dem import dem_on_grid

    assert_pre_event(ctx.osm_snapshot, ctx.event_datetime)
    flow_cfg = ctx.cfg.get("flowpath", {})
    resolution = float(flow_cfg.get("dem_res_m", 30))
    search_grid = make_grid((lon - 1, lat - 1, lon + 1, lat + 1), res=resolution)
    dem, search_grid = dem_on_grid(search_grid)
    transformer = Transformer.from_crs(4326, search_grid.crs, always_xy=True)
    start_x, start_y = transformer.transform(lon, lat)
    path = flowpath_from_dem(dem, search_grid, start_x, start_y,
                             max_length_m=float(flow_cfg.get("max_length_km", 150)) * 1000)
    path_frame = gpd.GeoDataFrame({"start_lon": [lon], "start_lat": [lat],
                                   "length_km": [path.length / 1000]}, geometry=[path], crs=search_grid.crs)
    output = path_frame.to_crs(ctx.grid.crs)
    output.to_file(ctx.path("flowpath"), driver="GPKG")

    buffer_m = float(flow_cfg.get("settlement_buffer_m", 500))
    query_area = gpd.GeoSeries([path.buffer(buffer_m)], crs=search_grid.crs).to_crs(4326).iloc[0]
    places = fetch_layer(query_area, "places", ctx.osm_snapshot, ctx.cfg).to_crs(search_grid.crs)
    near = places.loc[places.geometry.distance(path) <= buffer_m]
    names = sorted({str(name) for name in near["name"] if name})
    result = {"start_lon": lon, "start_lat": lat, "length_km": round(path.length / 1000, 2),
              "settlements": names}
    ctx.log(STAGE, event="complete", **result)
    return result


__all__ = ["flowpath_from_dem", "trace_flowpath"]

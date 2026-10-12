"""Stage `vectorize`: hazard classes -> polygons + per-class areas (UTM only). Owner: P2."""
from __future__ import annotations

import numpy as np
from pyproj import CRS

from cutoff.contracts import HAZARD_CLASS_NAMES, HAZARD_CLASSES, HazardClass as HC
from cutoff.runctx import RunContext


def class_areas_km2(cls: np.ndarray, transform, crs) -> dict[int, float]:
    """Area per class from pixel counts. Only valid in a metre-based conformal projection (UTM):
    Web Mercator inflates area by 1/cos^2(lat) (~1.29 at 28 N) and is refused."""
    crs = CRS.from_user_input(crs)
    if not crs.is_projected or crs.to_epsg() == 3857 or crs.axis_info[0].unit_name not in ("metre", "meter"):
        raise ValueError(f"area needs a metre-based UTM projection, got {crs}")
    px_km2 = abs(transform.a * transform.e) / 1e6
    vals, counts = np.unique(cls, return_counts=True)
    return {int(v): float(c * px_km2) for v, c in zip(vals, counts)}


def vectorize(cls: np.ndarray, transform, crs, keep=tuple(int(c) for c in HAZARD_CLASSES), min_px: int = 5,
              simplify_m: float = 5.0):
    import geopandas as gpd
    from rasterio.features import shapes
    from shapely.geometry import shape

    mask = np.isin(cls, keep)
    recs = [{"geometry": shape(g), "class": int(v)}
            for g, v in shapes(cls.astype(np.int16), mask=mask, transform=transform)]
    if not recs:
        return gpd.GeoDataFrame({"class": np.array([], np.int64), "area_m2": np.array([], float)},
                                geometry=gpd.GeoSeries([], crs=crs), crs=crs)
    gdf = gpd.GeoDataFrame(recs, geometry="geometry", crs=crs)
    gdf = gdf[gdf.area >= min_px * abs(transform.a * transform.e)].copy()
    gdf["geometry"] = gdf.geometry.simplify(simplify_m, preserve_topology=True)
    gdf = gdf[~gdf.is_empty & gdf.is_valid].copy()
    gdf["area_m2"] = gdf.area
    return gdf[["class", "area_m2", "geometry"]]


def stage_vectorize(ctx: RunContext) -> dict:
    """Reads: hazard_class.tif. Writes: hazard.gpkg (layer 'hazard', cols class, area_m2).

    Returns: {"area_km2_by_class": {class_name: km2}, "no_observation_km2": float}
    """
    from cutoff.geo import raster_io

    cls = raster_io.read(ctx, "hazard_class")
    areas = class_areas_km2(cls, ctx.grid.affine, ctx.grid.crs)
    gdf = vectorize(cls, ctx.grid.affine, ctx.grid.crs)
    path = ctx.path("hazard")
    if path.exists():
        path.unlink()
    gdf.to_file(path, layer="hazard", driver="GPKG", geometry_type="Polygon")
    by_name = {HAZARD_CLASS_NAMES[int(c)]: round(areas.get(int(c), 0.0), 4)
               for c in (*HAZARD_CLASSES, HC.PERMANENT_WATER)}
    out = {"area_km2_by_class": by_name, "no_observation_km2": round(areas.get(int(HC.NO_OBS), 0.0), 4)}
    ctx.log("vectorize", n_polygons=len(gdf), **out)
    return out

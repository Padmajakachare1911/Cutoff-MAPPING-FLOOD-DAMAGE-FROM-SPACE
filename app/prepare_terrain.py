"""Prepare native GLO-30 context, contours and auditable overlay registration.

Display derivatives never change satellite/model rasters. --review creates a
separate run and recomputes settlement anchors/access using the frozen rules.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

import contourpy
import geopandas as gpd
import numpy as np
from pyproj import Transformer
import rasterio
from shapely.geometry import LineString, box
import yaml

from cutoff.data.dem import dem_on_grid, glo30_tiles
from cutoff.geo.grid import Grid, make_grid
from cutoff.geo.network import build_graph, node_ways, stage_access
from cutoff.geo.settlements import stage_settlements
from cutoff.report.schema import Results
from cutoff.runctx import RunContext

ROOT = Path(__file__).resolve().parents[1]


def reviewed_run(source: Path) -> Path:
    target = source.parent / f"{source.name}_terrain_review"
    if not target.exists():
        shutil.copytree(source, target)
    results = Results.model_validate_json((target / "results.json").read_text(encoding="utf-8"))
    if results.run_id == target.name and (target / "display/review.json").exists():
        return target
    if results.run_id != source.name:
        raise ValueError(f"Unrecognized review directory: {target}")
    cfg = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    ctx = RunContext(target, target.name, tuple(results.inputs.aoi_bbox),
                     results.inputs.event_datetime, str(results.inputs.osm_snapshot),
                     results.inputs.mode, cfg, Grid.from_json(target / "grid.json"))
    stage_settlements(ctx)
    access = stage_access(ctx)["access"]
    payload = results.model_dump(mode="json")
    payload.update(run_id=target.name, created_utc=datetime.now(UTC).isoformat(), access=access)
    payload["warnings"].append(f"Terrain review of {source.name}: satellite/model rasters reused; building-cluster anchors and access recomputed. Red markers indicate inferred route loss, not observed settlement inundation.")
    validated = Results.model_validate(payload)
    (target / "results.json").write_text(validated.model_dump_json(indent=2), encoding="utf-8")
    # Never retain an old PDF with newly calculated access numbers.
    from cutoff.report.sitrep import render
    render(validated, target)
    (target / "display/review.json").write_text(json.dumps({"parent_run": source.name,
        "reused": "unchanged satellite, hazard, model and exposure outputs",
        "recomputed": "settlement anchors and A/B/C road access"}, indent=2))
    return target


def prepare(root: Path, cache: Path) -> None:
    display = root / "display"
    display.mkdir(exist_ok=True)
    results = Results.model_validate_json((root / "results.json").read_text(encoding="utf-8"))
    grid = make_grid(tuple(results.inputs.aoi_bbox), res=30, buffer_m=40000)
    dem_path = display / "terrain_dem.tif"
    if not dem_path.exists():
        print(f"{root.name}: obtaining wider native GLO-30 surface", flush=True)
        dem, _ = dem_on_grid(grid, tile_cache=cache / "dem/tiles")
        if not np.isfinite(dem).all():
            raise ValueError("Incomplete elevation coverage; no synthetic heights will be substituted")
        temporary = display / "terrain_dem.tmp.tif"
        with rasterio.open(temporary, "w", **grid.profile("float32", nodata=np.nan)) as dst:
            dst.write(dem, 1)
            dst.build_overviews([2, 4, 8, 16], rasterio.enums.Resampling.average)
        temporary.replace(dem_path)
    with rasterio.open(dem_path) as ds:
        grid = Grid(ds.crs.to_epsg(), tuple(ds.transform)[:6], ds.width, ds.height)
        # Elevation colours are a cartographic key, not an optical photograph.
        colour_dem = ds.read(1, out_shape=(ds.height//2, ds.width//2),
                             resampling=rasterio.enums.Resampling.average)
        stops = np.array([[188,206,184], [201,207,171], [212,202,177],
                          [199,185,168], [215,210,199], [241,241,237]])
        lo, hi = float(colour_dem.min()), float(colour_dem.max())
        scaled = np.clip((colour_dem-lo)/max(hi-lo, 1), 0, 1)
        colour = np.stack([np.interp(scaled, np.linspace(0, 1, len(stops)), stops[:,i])
                           for i in range(3)], axis=-1).astype("uint8")
        rgba = np.concatenate([colour, np.full((*colour.shape[:2], 1), 255, "uint8")], axis=2)
        profile = grid.profile("uint8", count=4)
        profile.update(width=rgba.shape[1], height=rgba.shape[0],
                       transform=ds.transform * rasterio.Affine.scale(ds.width/rgba.shape[1], ds.height/rgba.shape[0]))
        with rasterio.open(display / "terrain_relief.tif", "w", **profile) as dst:
            dst.write(np.moveaxis(rgba, -1, 0))
        # Contours only inside the study area plus 2 km, not the whole context.
        aoi = gpd.GeoSeries([box(*results.inputs.aoi_bbox)], crs=4326).to_crs(ds.crs).iloc[0].buffer(2000)
        window = rasterio.windows.from_bounds(*aoi.bounds, transform=ds.transform).round_offsets().round_lengths()
        elevation = ds.read(1, window=window)
        transform = ds.window_transform(window)
        xs = transform.c + (np.arange(elevation.shape[1]) + .5) * transform.a
        ys = transform.f + (np.arange(elevation.shape[0]) + .5) * transform.e
        step = 100 if np.ptp(elevation) > 1000 else 20
        generator = contourpy.contour_generator(x=xs, y=ys, z=elevation)
        lines, heights = [], []
        for level in np.arange(np.ceil(elevation.min()/step)*step, elevation.max(), step):
            for coords in generator.lines(float(level)):
                line = LineString(coords).simplify(8)
                if line.length >= 150:
                    lines.append(line); heights.append(int(level))
        if lines:
            gpd.GeoDataFrame({"elevation_m": heights, "index": [h % (step*5) == 0 for h in heights]},
                             geometry=lines, crs=ds.crs).to_file(display / "contours.gpkg", driver="GPKG")
    settlements = gpd.read_file(root / "settlements.gpkg")
    buildings = gpd.read_file(root / "osm_buildings.gpkg").to_crs(settlements.crs)
    roads = gpd.read_file(root / "osm_roads.gpkg").to_crs(settlements.crs)
    segments = node_ways(roads)
    graph = build_graph(segments)
    nodes = np.asarray([node[:2] for node in graph.nodes], dtype=float)
    from scipy.spatial import cKDTree
    tree = cKDTree(nodes) if len(nodes) else None
    distances = buildings.sindex.nearest(settlements.geometry, return_all=False, return_distance=True)[1]
    coordinates = [(p.x, p.y) for p in settlements.geometry]
    snaps = tree.query(coordinates)[0] if tree else np.full(len(coordinates), np.inf)
    with rasterio.open(root / "hazard_class.tif") as ds:
        codes = [int(v[0]) for v in ds.sample(coordinates)]
    annotations = {}
    for i, (_, row) in enumerate(settlements.iterrows()):
        annotations[row.sid] = {"location_source": str(row.source),
            "anchor_method": "Mapped OSM place point" if row.source == "osm_place" else
                ("Representative point inside mapped building" if distances[i] < .01 else "Original cluster mean between buildings"),
            "nearest_building_m": round(float(distances[i]), 1),
            "road_snap_m": round(float(snaps[i]), 1) if np.isfinite(snaps[i]) else None,
            "hazard_pixel_class": codes[i],
            "observed_flood_at_point": codes[i] in (1, 2)}
    audits = {}
    for scenario in "ABC":
        status = gpd.read_file(root / f"settlements_{scenario}.gpkg")
        original = settlements.set_index("sid")
        registered = all(row.geometry.equals_exact(original.loc[row.sid].geometry, 1e-6) for _, row in status.iterrows())
        closures = gpd.read_file(root / f"roads_status_{scenario}.gpkg")
        closed = closures[closures.closed.astype(bool)]
        # Lines must remain on actual pre-event OSM roads (allow 1 mm roundoff).
        road_index = roads.sindex
        def on_source(line):
            candidates = road_index.query(line.buffer(.001), predicate="intersects")
            return any(geometry.buffer(.001).covers(line) for geometry in roads.geometry.iloc[candidates])
        roads_registered = all(on_source(line) for line in closed.geometry)
        audits[scenario] = {"markers_equal_analysis_coordinates": registered,
                           "closures_on_source_road_centerlines": roads_registered,
                           "closed_segments": len(closed), "status_counts": status.status.value_counts().to_dict(),
                           "cut_off_at_flood_pixel": sum(annotations[r.sid]["observed_flood_at_point"] for _, r in status[status.status.eq("cut_off")].iterrows())}
        if not registered or not roads_registered:
            raise ValueError(f"Overlay registration failed for scenario {scenario}")
    metadata = {"source": "Copernicus GLO-30 surface model", "native_resolution_m": 30,
        "display_grid_m": 30, "vertical_scale": 1, "buffer_m": 40000,
        "bounds": grid.bounds_wgs84(), "tiles": glo30_tiles(grid.bounds_wgs84()),
        "contour_interval_m": step, "prepared_utc": datetime.now(UTC).isoformat(),
        "elevation_range_m": [round(lo, 1), round(hi, 1)],
        "limitations": "30 m surface model includes vegetation/buildings; no surveyed building heights. Red markers mean scenario-based road-access loss, not direct inundation.",
        "scenarios": audits, "markers": annotations}
    (display / "terrain.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"{root.name}: terrain and overlay audit ready {json.dumps(audits)}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--cache", type=Path, default=Path("C:/cutoff_data/cache"))
    parser.add_argument("--review", action="store_true")
    args = parser.parse_args()
    for root in args.runs:
        prepare(reviewed_run(root) if args.review else root, args.cache)

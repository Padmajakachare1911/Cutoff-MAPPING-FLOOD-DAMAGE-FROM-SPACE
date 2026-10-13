from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import yaml
from pyproj import Transformer
from shapely.geometry import Point

from cutoff.contracts_check import validate_run_dir
from cutoff.geo import flowpath
from cutoff.geo.flowpath import flowpath_from_dem
from cutoff.geo.grid import Grid
from cutoff.mock import MOCK_BBOX, make_mock_run
from cutoff.runctx import RunContext


def test_tilted_valley_path_reaches_low_outlet():
    size = 30
    rows, cols = np.mgrid[:size, :size]
    dem = (size - rows) + np.abs(cols - size // 2) * 3
    grid = Grid(32645, (30, 0, 0, 0, -30, size * 30), size, size)
    start_x = (size // 2 + 0.5) * 30
    start_y = (size - 0.5) * 30

    path = flowpath_from_dem(dem.astype(np.float32), grid, start_x, start_y,
                             stream_upa_km2=0, max_length_m=5000)

    assert path.coords[-1][1] < 60
    assert path.length >= 800


def test_trace_flowpath_writes_contract_and_lists_nearby_place(tmp_path, monkeypatch):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    ctx = RunContext(run_dir, "mock", MOCK_BBOX, datetime(2026, 8, 26, 2, 52, tzinfo=UTC),
                     "2026-07-27T00:00:00Z", "cached", cfg, Grid.from_json(run_dir / "grid.json"))
    grid = Grid(ctx.grid.epsg, (30, 0, ctx.grid.bounds[0], 0, -30, ctx.grid.bounds[3]), 30, 30)
    rows, cols = np.mgrid[:30, :30]
    dem = ((30 - rows) + np.abs(cols - 15) * 3).astype(np.float32)
    to_ll = Transformer.from_crs(grid.crs, 4326, always_xy=True)
    start_x, start_y = grid.bounds[0] + 465, grid.bounds[3] - 15
    start_lon, start_lat = to_ll.transform(start_x, start_y)
    place = gpd.GeoDataFrame({"osm_id": ["node/1"], "place": ["village"], "name": ["Downstream"]},
                             geometry=[Point(start_x, grid.bounds[3] - 855)], crs=grid.crs).to_crs(4326)
    monkeypatch.setattr(flowpath, "make_grid", lambda *args, **kwargs: grid)
    monkeypatch.setattr("cutoff.data.dem.dem_on_grid", lambda _: (dem, grid))
    monkeypatch.setattr(flowpath, "fetch_layer", lambda *args, **kwargs: place)

    result = flowpath.trace_flowpath(ctx, start_lon, start_lat)

    assert result["settlements"] == ["Downstream"]
    validate_run_dir(run_dir, keys=["flowpath"], require_optional=True)

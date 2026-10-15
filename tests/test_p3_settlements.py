from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import yaml
from shapely.geometry import Point, box

from cutoff.contracts_check import validate_run_dir
from cutoff.geo.grid import Grid
from cutoff.geo.settlements import derive_settlements, derive_targets, stage_settlements
from cutoff.mock import MOCK_BBOX, make_mock_run
from cutoff.runctx import RunContext

CRS = 32645


def _buildings(n):
    geoms = [box(i * 8 - 2, -2, i * 8 + 2, 2) for i in range(n)]
    return gpd.GeoDataFrame({"osm_id": [f"way/{i}" for i in range(n)]}, geometry=geoms, crs=CRS)


def test_six_buildings_make_cluster_but_four_do_not():
    empty_places = gpd.GeoDataFrame({"osm_id": [], "place": [], "name": []}, geometry=[], crs=CRS)
    aoi = box(-100, -100, 100, 100)

    assert len(derive_settlements(empty_places, _buildings(6), aoi)) == 1
    assert len(derive_settlements(empty_places, _buildings(4), aoi)) == 0


def test_cluster_anchor_is_inside_a_member_building_not_between_buildings():
    empty = gpd.GeoDataFrame({"place": [], "name": []}, geometry=[], crs=CRS)
    buildings = gpd.GeoDataFrame(geometry=[box(x-2,y-2,x+2,y+2) for x,y in
        [(-30,-30),(-30,0),(-30,30),(0,30),(30,30),(30,0),(30,-30)]], crs=CRS)
    mean = buildings.geometry.centroid.union_all().centroid
    assert not buildings.geometry.union_all().covers(mean)
    settlement = derive_settlements(empty, buildings, box(-100,-100,100,100)).iloc[0]
    assert buildings.geometry.union_all().covers(settlement.geometry)
    assert settlement.n_buildings == 7


def test_named_osm_location_is_preserved_exactly():
    point = Point(3, 19)
    places = gpd.GeoDataFrame({"place": ["village"], "name": ["Named"]}, geometry=[point], crs=CRS)
    assert derive_settlements(places, _buildings(6), box(-100,-100,100,100)).iloc[0].geometry.equals_exact(point, 0)


def test_nearby_place_suppresses_building_cluster_and_counts_buildings():
    places = gpd.GeoDataFrame(
        {"osm_id": ["node/1"], "place": ["village"], "name": ["Named"]},
        geometry=[Point(0, 0)], crs=CRS,
    )
    got = derive_settlements(places, _buildings(6), box(-100, -100, 100, 100))

    assert len(got) == 1
    assert got.iloc[0].source == "osm_place"
    assert got.iloc[0].n_buildings == 6


def test_outside_place_is_target_but_not_settlement():
    places = gpd.GeoDataFrame(
        {"osm_id": ["node/1"], "place": ["town"], "name": ["Outside"]},
        geometry=[Point(500, 0)], crs=CRS,
    )
    health = gpd.GeoDataFrame({"osm_id": [], "kind": [], "name": []}, geometry=[], crs=CRS)

    settlements = derive_settlements(places, _buildings(0), box(-100, -100, 100, 100))
    targets = derive_targets(places, health)

    assert settlements.empty
    assert targets.name.tolist() == ["Outside"]
    assert targets.kind.tolist() == ["town"]


def test_stage_settlements_validates_on_mock_run(tmp_path):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    ctx = RunContext(run_dir, "mock", MOCK_BBOX, datetime(2026, 8, 26, 2, 52, tzinfo=UTC),
                     "2026-07-27T00:00:00Z", "cached", cfg, Grid.from_json(run_dir / "grid.json"))

    result = stage_settlements(ctx)

    assert result["n_settlements"] >= 4
    assert result["n_targets"] == 1
    validate_run_dir(run_dir, keys=["settlements", "targets"])

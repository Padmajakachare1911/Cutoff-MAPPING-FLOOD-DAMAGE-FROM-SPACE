from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pytest
import yaml
from shapely.geometry import LineString, box

from cutoff.contracts_check import validate_run_dir
from cutoff.geo.exposure import exposed_bridge_counts, exposed_buildings, exposed_roads, stage_exposure
from cutoff.geo.grid import Grid
from cutoff.mock import MOCK_BBOX, make_mock_run
from cutoff.runctx import RunContext

CRS = 32645


def test_building_uses_highest_priority_touched_class():
    buildings = gpd.GeoDataFrame({"osm_id": ["way/1"]}, geometry=[box(0, 0, 10, 10)], crs=CRS)
    hazard = gpd.GeoDataFrame({"class": [2, 4, 1]}, geometry=[box(0, 0, 3, 3), box(2, 2, 6, 6), box(8, 8, 12, 12)], crs=CRS)

    got = exposed_buildings(buildings, hazard)

    assert got.hazard_class.tolist() == [1]


def test_road_intersection_length_and_bridge_buffer():
    roads = gpd.GeoDataFrame({"osm_id": ["way/1"], "bridge": [True]},
                             geometry=[LineString([(0, 0), (100, 0)])], crs=CRS)
    hazard = gpd.GeoDataFrame({"class": [4]}, geometry=[box(25, -10, 75, 10)], crs=CRS)

    exposed = exposed_roads(roads, hazard)
    bridge_counts = exposed_bridge_counts(roads, hazard)

    assert exposed.length_m.sum() == pytest.approx(50)
    assert bridge_counts["rule_increase"] == 1


def test_stage_exposure_validates_on_mock_run(tmp_path):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    ctx = RunContext(run_dir, "mock", MOCK_BBOX, datetime(2026, 8, 26, 2, 52, tzinfo=UTC),
                     "2026-07-27T00:00:00Z", "cached", cfg, Grid.from_json(run_dir / "grid.json"))

    result = stage_exposure(ctx)

    assert sum(result["buildings_by_class"].values()) == 3
    validate_run_dir(run_dir, keys=["exposure_buildings", "exposure_roads"])

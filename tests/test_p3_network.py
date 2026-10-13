from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import yaml
from shapely.geometry import LineString, Point, box

from cutoff.contracts_check import validate_run_dir
from cutoff.geo.grid import Grid
from cutoff.geo.network import access_status, build_graph, closed_segments, edge_dropout, node_ways, stage_access
from cutoff.mock import MOCK_BBOX, make_mock_run
from cutoff.runctx import RunContext

CRS = 32645


def _roads(geometries, **columns):
    count = len(geometries)
    data = {"osm_id": [f"way/{i}" for i in range(count)], "highway": ["primary"] * count,
            "tier": ["road"] * count, "bridge": [False] * count, "name": [""] * count,
            "layer": ["0"] * count, "tunnel": [False] * count}
    data.update(columns)
    return gpd.GeoDataFrame(data, geometry=geometries, crs=CRS)


def _toy_network():
    roads = _roads([LineString([(0, 0), (4000, 0)]), LineString([(1000, -500), (1000, 500)])])
    settlements = gpd.GeoDataFrame({"sid": ["W", "E", "O"], "name": ["West", "East", "Orphan"]},
                                    geometry=[Point(0, 0), Point(4000, 0), Point(9000, 9000)], crs=CRS)
    targets = gpd.GeoDataFrame({"tid": ["T"], "name": ["Hospital"]}, geometry=[Point(1000, 500)], crs=CRS)
    hazard = gpd.GeoDataFrame({"class": [1]}, geometry=[box(3400, -20, 3600, 20)], crs=CRS)
    return roads, settlements, targets, hazard


def test_noding_limits_closure_and_assigns_expected_statuses():
    roads, settlements, targets, hazard = _toy_network()
    segments = node_ways(roads)
    graph = build_graph(segments)
    closed = closed_segments(segments, hazard, "A")
    status = access_status(graph, settlements, targets, closed).set_index("name").status

    assert len(segments) == 50
    assert len(closed) == 4
    assert status.to_dict() == {"West": "connected", "East": "cut_off", "Orphan": "unknown"}


def test_grade_separated_bridge_is_not_noded_and_approaches_control_scenario_c():
    roads = _roads(
        [LineString([(0, 0), (100, 0)]), LineString([(50, -50), (50, 50)])],
        bridge=[True, False], layer=["1", "0"],
    )
    segments = node_ways(roads, 200)
    middle = gpd.GeoDataFrame({"class": [1]}, geometry=[box(45, -5, 55, 5)], crs=CRS)
    approach = gpd.GeoDataFrame({"class": [1]}, geometry=[box(-5, -5, 5, 5)], crs=CRS)

    assert len(segments) == 2
    assert closed_segments(segments, middle, "C") == set()
    assert closed_segments(segments, approach, "C") == {0}


def test_multigraph_keeps_parallel_edges_and_dropout_is_non_mutating():
    roads = _roads([LineString([(0, 0), (100, 0)]), LineString([(0, 0), (100, 0)])])
    segments = node_ways(roads, 200)
    graph = build_graph(segments)

    assert isinstance(graph, nx.MultiGraph)
    assert graph.number_of_edges() == 2
    dropped = edge_dropout(graph, 0.5, np.random.default_rng(0))
    assert dropped.number_of_edges() == 1
    assert graph.number_of_edges() == 2


def test_degraded_when_closure_forces_long_detour():
    roads = _roads([
        LineString([(0, 0), (100, 0)]),
        LineString([(0, 0), (0, 200), (100, 200), (100, 0)]),
    ])
    segments = node_ways(roads, 100)
    graph = build_graph(segments)
    settlements = gpd.GeoDataFrame({"sid": ["S"], "name": ["Village"]}, geometry=[Point(0, 0)], crs=CRS)
    targets = gpd.GeoDataFrame({"tid": ["T"]}, geometry=[Point(100, 0)], crs=CRS)

    got = access_status(graph, settlements, targets, {0})

    assert got.iloc[0].status == "degraded"


def test_stage_access_validates_on_mock_run(tmp_path):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    ctx = RunContext(run_dir, "mock", MOCK_BBOX, datetime(2026, 8, 26, 2, 52, tzinfo=UTC),
                     "2026-07-27T00:00:00Z", "cached", cfg, Grid.from_json(run_dir / "grid.json"))

    result = stage_access(ctx)

    assert [item["scenario"] for item in result["access"]] == ["A", "B", "C"]
    validate_run_dir(run_dir, keys=["settlements_A", "settlements_B", "settlements_C",
                                    "roads_A", "roads_B", "roads_C"])

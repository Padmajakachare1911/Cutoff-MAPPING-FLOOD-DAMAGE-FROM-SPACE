import inspect
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import httpx
import pytest
import yaml
from shapely.geometry import LineString, Point, box

from cutoff.contracts_check import validate_run_dir
from cutoff.data import osm
from cutoff.data.osm import assert_pre_event, fetch_layer, parse_layer, stage_osm
from cutoff.geo.grid import Grid
from cutoff.mock import MOCK_BBOX, make_mock_run
from cutoff.runctx import RunContext

EVENT = datetime(2026, 8, 26, 2, 52, tzinfo=UTC)


def test_assert_pre_event_rejects_latest_and_post_event():
    assert_pre_event("2026-07-27T00:00:00Z", EVENT)
    with pytest.raises(ValueError, match="latest"):
        assert_pre_event("latest", EVENT)
    with pytest.raises(ValueError, match="before"):
        assert_pre_event("2026-08-26T03:00:00Z", EVENT)


def test_parse_roads_flattens_tags_and_derives_contract_fields():
    raw = gpd.GeoDataFrame(
        {
            "@osmId": ["way/1", "way/2", "way/3"],
            "tags": [
                {"highway": "primary", "bridge": "yes", "name": "A"},
                {"highway": "track"},
                {"highway": "footway", "bridge": "no"},
            ],
        },
        geometry=[LineString([(0, 0), (1, 0)])] * 3,
        crs=4326,
    )

    got = parse_layer(raw, "roads")

    assert got.osm_id.tolist() == ["way/1", "way/2", "way/3"]
    assert got.tier.tolist() == ["road", "track", "trail"]
    assert got.bridge.tolist() == [True, False, False]
    assert got.name.tolist() == ["A", "", ""]


def test_source_never_requests_latest():
    source = inspect.getsource(osm)
    assert '"time": "latest"' not in source
    assert "'time': 'latest'" not in source


def test_fetch_layer_falls_back_to_v1_after_three_v2_503s(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append(url)
        request = httpx.Request("POST", url)
        if "v2" in url:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "properties": {"@osmId": "way/7", "tags": {"highway": "track"}},
                    "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 0]]},
                }],
            },
        )

    monkeypatch.setattr(osm.httpx, "post", fake_post)
    monkeypatch.setattr(osm.time, "sleep", lambda _: None)
    cfg = {"osm": {"api_v2": "https://test/v2", "api_v1": "https://test/v1"}}
    monkeypatch.setenv("OHSOME_API_KEY", "test-key")

    got = fetch_layer(box(0, 0, 1, 1), "roads", "2026-07-27T00:00:00Z", cfg)

    assert calls == ["https://test/v2/extraction/features.parquet"] * 3 + ["https://test/v1/elements/geometry"]
    assert got.attrs["osm_api"] == "v1"
    assert got.loc[0, "tier"] == "track"


def test_stage_osm_tiles_deduplicates_and_validates_outputs(tmp_path, monkeypatch):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    ctx = RunContext(run_dir, "mock", MOCK_BBOX, EVENT, "2026-07-27T00:00:00Z", "fast", cfg,
                     Grid.from_json(run_dir / "grid.json"))

    def fake_fetch(_aoi, layer, *_args):
        if layer == "roads":
            frame = gpd.GeoDataFrame({"osm_id": ["way/1"], "highway": ["primary"], "tier": ["road"],
                                      "bridge": [False], "name": ["Road"], "layer": ["0"], "tunnel": [False]},
                                     geometry=[LineString([(85.33, 28.15), (85.34, 28.16)])], crs=4326)
        elif layer == "buildings":
            frame = gpd.GeoDataFrame({"osm_id": ["way/2"]}, geometry=[box(85.33, 28.15, 85.331, 28.151)], crs=4326)
        elif layer == "places":
            frame = gpd.GeoDataFrame({"osm_id": ["node/3"], "place": ["village"], "name": ["Village"]},
                                     geometry=[Point(85.33, 28.15)], crs=4326)
        else:
            frame = gpd.GeoDataFrame({"osm_id": ["node/4"], "kind": ["hospital"], "name": ["Hospital"]},
                                     geometry=[Point(85.34, 28.16)], crs=4326)
        frame.attrs["osm_api"] = "v2"
        return frame

    monkeypatch.setattr(osm, "fetch_layer", fake_fetch)
    result = stage_osm(ctx)

    assert result["counts"] == {"roads": 1, "buildings": 1, "places": 1, "health": 1}
    validate_run_dir(run_dir, keys=["osm_roads", "osm_buildings", "osm_places", "osm_health"])

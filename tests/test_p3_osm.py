import inspect
from datetime import UTC, datetime

import geopandas as gpd
import httpx
import pytest
from shapely.geometry import LineString, box

from cutoff.data import osm
from cutoff.data.osm import assert_pre_event, fetch_layer, parse_layer

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

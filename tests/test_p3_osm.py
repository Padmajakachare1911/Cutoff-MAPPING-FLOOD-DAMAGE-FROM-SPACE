import inspect
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd
import pytest
import yaml
from shapely.geometry import LineString, Point, box

from cutoff.contracts_check import validate_run_dir
from cutoff.data import osm
from cutoff.data.osm import (
    _snapshot_slug,
    assert_pre_event,
    fetch_layer,
    parse_layer,
    stage_osm,
)
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


def test_recorded_v2_roads_fixture_parses_contract_fields():
    fixture = Path(__file__).parent / "fixtures" / "ohsome_roads_sample.parquet"
    raw = gpd.read_parquet(fixture, to_pandas_kwargs={"maps_as_pydicts": "strict"})

    got = parse_layer(raw, "roads")

    assert len(got) == 580
    assert got.osm_id.str.startswith("way/").all()
    assert set(got.tier) <= {"road", "track", "trail"}
    assert got.bridge.dtype == bool


def test_parse_roads_excludes_highway_areas_from_routing():
    raw = gpd.GeoDataFrame(
        {"@osmId": ["way/1", "way/2"], "tags": [{"highway": "unclassified"}] * 2},
        geometry=[LineString([(0, 0), (1, 0)]), box(0, 0, 1, 1)], crs=4326,
    )
    got = parse_layer(raw, "roads")
    assert got.osm_id.tolist() == ["way/1"]
    assert got.geom_type.tolist() == ["LineString"]


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


@pytest.mark.parametrize("retry_after, expected_wait", [(None, 60.0), ("5", 60.0), ("75", 75.0)])
def test_v2_rate_limit_waits_for_window_then_recovers(monkeypatch, retry_after, expected_wait):
    calls, waits = [], []

    def fake_post(url, **kwargs):
        calls.append(url)
        headers = {"retry-after": retry_after} if retry_after else {}
        return httpx.Response(429 if len(calls) == 1 else 200,
                              headers=headers, request=httpx.Request("POST", url))

    monkeypatch.setenv("OHSOME_API_KEY", "test-key")
    monkeypatch.setattr(osm.httpx, "post", fake_post)
    monkeypatch.setattr(osm.time, "sleep", waits.append)
    monkeypatch.setattr(osm, "_read_v2", lambda _: gpd.GeoDataFrame(geometry=[], crs=4326))

    got = osm._request_v2(box(0, 0, 1, 1), "roads", "2026-07-27T00:00:00Z", {})

    assert waits == [expected_wait]
    assert len(calls) == 2 and got.attrs["osm_api"] == "v2"


def test_stage_osm_tiles_deduplicates_and_validates_outputs(tmp_path, monkeypatch):
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    cfg["osm"]["request_delay_s"] = 0
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


# â”€â”€ Issue #25: snapshot slug is included in _cache_dir â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def test_snapshot_slug_strips_colons_and_is_filesystem_safe():
    """_snapshot_slug must produce a safe name that differs between dates (fix #25)."""
    slug1 = _snapshot_slug("2026-07-01T00:00:00Z")
    slug2 = _snapshot_slug("2026-07-27T00:00:00Z")
    assert ":" not in slug1
    assert "+" not in slug1
    assert slug1 != slug2


def test_cache_dir_differs_for_different_snapshot_dates(tmp_path, monkeypatch):
    """Two runs with the same grid but different snapshots must use different cache dirs (fix #25)."""
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    grid = Grid.from_json(run_dir / "grid.json")

    ctx_a = RunContext(run_dir, "mock", MOCK_BBOX, EVENT, "2026-07-01T00:00:00Z", "fast", cfg, grid)
    ctx_b = RunContext(run_dir, "mock", MOCK_BBOX, EVENT, "2026-07-27T00:00:00Z", "fast", cfg, grid)

    from cutoff.data.osm import _cache_dir

    assert _cache_dir(ctx_a) != _cache_dir(ctx_b), (
        "_cache_dir must differ between snapshot dates to prevent silent cache reuse"
    )


# â”€â”€ Issue #31: stale-cache fallback when both APIs fail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _make_minimal_roads_frame() -> gpd.GeoDataFrame:
    frame = gpd.GeoDataFrame(
        {"osm_id": ["way/99"], "highway": ["primary"], "tier": ["road"],
         "bridge": [False], "name": ["OldRoad"], "layer": ["0"], "tunnel": [False]},
        geometry=[LineString([(85.33, 28.15), (85.34, 28.16)])],
        crs=4326,
    )
    return frame


@pytest.mark.parametrize('other_snapshot', ['2026-06-01T00:00:00Z', '2026-09-01T00:00:00Z'])
def test_stage_osm_rejects_other_snapshot_cache_when_apis_fail(tmp_path, monkeypatch, other_snapshot):
    """An API failure cannot change source dates, including to post-event data."""
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    cfg["osm"]["request_delay_s"] = 0
    grid = Grid.from_json(run_dir / "grid.json")

    # Plant a stale cache (different snapshot slug) for every layer.
    from cutoff.data.osm import _snapshot_slug
    from cutoff.data.s1_acquire import grid_hash

    stale_slug = _snapshot_slug(other_snapshot)
    grid_cache = Path(cfg["run"]["cache_dir"]) / "osm" / grid_hash(grid)
    stale_dir = grid_cache / stale_slug
    stale_dir.mkdir(parents=True, exist_ok=True)

    roads_frame = _make_minimal_roads_frame()
    for layer_name in ["roads", "buildings", "places", "health"]:
        if layer_name == "buildings":
            f = gpd.GeoDataFrame({"osm_id": ["way/2"]}, geometry=[box(85.33, 28.15, 85.331, 28.151)], crs=4326)
        elif layer_name == "places":
            f = gpd.GeoDataFrame({"osm_id": ["node/3"], "place": ["village"], "name": ["V"]},
                                 geometry=[Point(85.33, 28.15)], crs=4326)
        elif layer_name == "health":
            f = gpd.GeoDataFrame({"osm_id": ["node/4"], "kind": ["hospital"], "name": ["H"]},
                                 geometry=[Point(85.34, 28.16)], crs=4326)
        else:
            f = roads_frame.copy()
        f.to_parquet(stale_dir / f"{layer_name}.parquet")

    # Make fetch_layer always fail (simulates no OHSOME_API_KEY + 403 on v1).
    monkeypatch.setattr(osm, "fetch_layer", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("API unavailable")))

    warnings = []

    ctx = RunContext(run_dir, "mock", MOCK_BBOX, EVENT, "2026-07-27T00:00:00Z", "fast", cfg, grid)
    monkeypatch.setattr(ctx, "warn", lambda _stage, msg: warnings.append(msg))

    with pytest.raises(RuntimeError, match='API unavailable'):
        stage_osm(ctx)
    assert not any('MAY NOT MATCH' in w for w in warnings)


def test_cache_dir_normalizes_offsets_and_preserves_distinct_times(tmp_path):
    from cutoff.data.osm import _cache_dir
    run = make_mock_run(tmp_path / 'mock')
    cfg = yaml.safe_load((Path(__file__).parents[1] / 'configs/default.yaml').read_text())
    cfg['run']['cache_dir'] = str(tmp_path / 'cache')
    grid = Grid.from_json(run / 'grid.json')
    def ctx(snapshot):
        return RunContext(run, 'mock', MOCK_BBOX, EVENT, snapshot, 'cached', cfg, grid)
    assert _cache_dir(ctx('2026-07-27T00:00:00+05:30')) != _cache_dir(ctx('2026-07-27T00:00:00+04:30'))
    assert _cache_dir(ctx('2026-07-27T00:00:00+05:30')) == _cache_dir(ctx('2026-07-26T18:30:00Z'))
    assert _cache_dir(ctx('2026-07-27T00:00:00.1Z')) != _cache_dir(ctx('2026-07-27T00:00:00.2Z'))


def test_cache_dir_changes_with_routing_coverage(tmp_path):
    import copy

    from cutoff.data.osm import _cache_dir
    run = make_mock_run(tmp_path / 'mock')
    cfg = yaml.safe_load((Path(__file__).parents[1] / 'configs/default.yaml').read_text())
    cfg['run']['cache_dir'] = str(tmp_path / 'cache')
    cfg2 = copy.deepcopy(cfg)
    cfg2['access']['access_buffer_km'] = cfg['access']['access_buffer_km'] + 1
    grid = Grid.from_json(run / 'grid.json')
    a = RunContext(run, 'mock', MOCK_BBOX, EVENT, '2026-07-27T00:00:00Z', 'cached', cfg, grid)
    b = RunContext(run, 'mock', MOCK_BBOX, EVENT, '2026-07-27T00:00:00Z', 'cached', cfg2, grid)
    assert _cache_dir(a) != _cache_dir(b)


def test_stage_osm_reuses_only_matching_cache(tmp_path):
    from cutoff.data.osm import _cache_dir
    run = make_mock_run(tmp_path / 'mock')
    cfg = yaml.safe_load((Path(__file__).parents[1] / 'configs/default.yaml').read_text())
    cfg['run']['cache_dir'] = str(tmp_path / 'cache')
    ctx = RunContext(run, 'mock', MOCK_BBOX, EVENT, '2026-07-27T00:00:00Z', 'cached', cfg,
                     Grid.from_json(run / 'grid.json'))
    cache = _cache_dir(ctx)
    cache.mkdir(parents=True)
    for layer in ['roads', 'buildings', 'places', 'health']:
        gpd.read_file(ctx.path('osm_' + layer)).to_crs(4326).to_parquet(cache / (layer + '.parquet'))
    result = stage_osm(ctx)
    assert result['osm_api'] == 'cache' and result['osm_snapshot'] == ctx.osm_snapshot
    assert not ctx.warnings  # intentional offline reuse is not an API outage
    validate_run_dir(run, keys=['osm_roads', 'osm_buildings', 'osm_places', 'osm_health'])


def test_cached_highway_area_does_not_reach_network(tmp_path):
    from cutoff.data.osm import _cache_dir
    from cutoff.geo.network import node_ways

    run = make_mock_run(tmp_path / 'mock')
    cfg = yaml.safe_load((Path(__file__).parents[1] / 'configs/default.yaml').read_text())
    cfg['run']['cache_dir'] = str(tmp_path / 'cache')
    ctx = RunContext(run, 'mock', MOCK_BBOX, EVENT, '2026-07-27T00:00:00Z', 'cached', cfg,
                     Grid.from_json(run / 'grid.json'))
    cache = _cache_dir(ctx)
    cache.mkdir(parents=True)
    for layer in ['roads', 'buildings', 'places', 'health']:
        frame = gpd.read_file(ctx.path('osm_' + layer)).to_crs(4326)
        if layer == 'roads':
            area = frame.iloc[[0]].copy()
            area['osm_id'] = 'way/area'
            area.geometry = [box(85.33, 28.15, 85.331, 28.151)]
            frame = gpd.GeoDataFrame(pd.concat([frame, area]), crs=4326)
        frame.to_parquet(cache / (layer + '.parquet'))
    stage_osm(ctx)
    roads = gpd.read_file(ctx.path('osm_roads'))
    assert 'way/area' not in roads.osm_id.tolist()
    assert not node_ways(roads).empty

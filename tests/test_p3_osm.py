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
from cutoff.data.osm import _snapshot_slug, assert_pre_event, fetch_layer, parse_layer, stage_osm
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


# ── Issue #25: snapshot slug is included in _cache_dir ─────────────────────────


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


# ── Issue #31: stale-cache fallback when both APIs fail ─────────────────────────


def _make_minimal_roads_frame() -> gpd.GeoDataFrame:
    frame = gpd.GeoDataFrame(
        {"osm_id": ["way/99"], "highway": ["primary"], "tier": ["road"],
         "bridge": [False], "name": ["OldRoad"], "layer": ["0"], "tunnel": [False]},
        geometry=[LineString([(85.33, 28.15), (85.34, 28.16)])],
        crs=4326,
    )
    return frame


def test_stage_osm_falls_back_to_stale_snapshot_cache_when_apis_fail(tmp_path, monkeypatch):
    """When both v2 and v1 fail and no same-snapshot cache exists, stage_osm must
    fall back to any parquet in an older snapshot sub-directory rather than raising (fix #31).
    """
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())
    cfg["run"]["cache_dir"] = str(tmp_path / "cache")
    cfg["osm"]["request_delay_s"] = 0
    grid = Grid.from_json(run_dir / "grid.json")

    # Plant a stale cache (different snapshot slug) for every layer.
    from cutoff.data.s1_acquire import cache_root, grid_hash
    from cutoff.data.osm import _snapshot_slug

    stale_slug = _snapshot_slug("2026-06-01T00:00:00Z")
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

    # Should NOT raise; should fall back to stale cache.
    result = stage_osm(ctx)

    assert result["osm_api"] == "cache"
    assert result["counts"]["roads"] >= 1
    # At least one warning must mention the stale-snapshot fallback.
    assert any("MAY NOT MATCH" in w for w in warnings), f"Expected stale-cache warning, got: {warnings}"

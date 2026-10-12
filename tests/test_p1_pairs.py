"""P1.1 - STAC scenes + same-track pair selection, offline against the recorded CDSE fixture."""
import copy
import dataclasses
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cutoff.data.cdse import Scene, scenes_from_items
from cutoff.data.s1_pairs import NoValidPair, select_pairs

FIXTURE = Path(__file__).parent / "fixtures" / "stac_trishuli_s1.json"
# An AOI inside the fixture bbox that all three tracks cover fully (121D's west edge runs diagonally
# through 85.31-85.36E, so it covers only ~55 % of trishuli_north - see test_coverage_rejects_121d_on_trishuli_north).
AOI_ALL_TRACKS = (85.40, 28.05, 85.50, 28.25)
TRISHULI_NORTH = (85.28, 28.10, 85.42, 28.29)
EVENT = datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc)


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@pytest.fixture(scope="module")
def items():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def scenes(items):
    return scenes_from_items(items, AOI_ALL_TRACKS)


def test_fixture_has_16_items_on_three_tracks(items, scenes):
    assert len(items) == 16 and len(scenes) == 16
    tracks = {(s.rel_orbit, s.direction) for s in scenes}
    assert tracks == {(85, "ascending"), (19, "descending"), (121, "descending")}
    assert all(s.platform == "sentinel-1d" and s.pols == ("VV", "VH") for s in scenes)
    assert all(s.coverage > 0.99 for s in scenes)
    s = next(s for s in scenes if s.datetime.date().isoformat() == "2026-08-28")
    assert s.start == utc("2026-08-28T12:21:41.762029Z") and s.end == utc("2026-08-28T12:22:06.760553Z")
    assert {"vv", "vh", "Product", "schema-calibration-vv"} <= set(s.assets)
    assert "thumbnail" not in s.assets


def test_trishuli_event_picks_85_ascending(scenes):
    pairs = select_pairs(scenes, EVENT)
    best = pairs[0]
    assert (best["rel_orbit"], best["direction"]) == (85, "ascending")
    assert best["post"].datetime == utc("2026-08-28T12:21:41.762029Z")
    assert [p.datetime.date().isoformat() for p in best["pre"]] == ["2026-08-16", "2026-08-04", "2026-07-23"]
    assert best["post_lag_hours"] == pytest.approx(57.5, abs=0.05)
    assert best["cross_track"] is False
    # every candidate is same-track, post strictly after the event, pre strictly before it
    for c in pairs:
        assert all((p.rel_orbit, p.direction) == (c["rel_orbit"], c["direction"]) for p in c["pre"] + [c["post"]])
        assert c["post"].datetime > EVENT and all(p.datetime < EVENT for p in c["pre"])
    # ranking: earliest post first
    assert [c["post"].datetime for c in pairs] == sorted(c["post"].datetime for c in pairs)


def test_post_must_be_strictly_after_event(scenes):
    best = select_pairs(scenes, utc("2026-08-28T13:00:00Z"))[0]
    assert best["post"].datetime.date().isoformat() == "2026-08-31"
    assert (best["rel_orbit"], best["direction"]) == (121, "descending")
    assert [p.datetime.date().isoformat() for p in best["pre"]] == ["2026-08-19", "2026-08-07", "2026-07-26"]
    assert all(c["post"].datetime.date().isoformat() != "2026-08-28" for c in select_pairs(scenes, utc("2026-08-28T13:00:00Z")))


def test_only_cross_track_raises_with_tracks_and_next_pass(scenes):
    post = [s for s in scenes if s.datetime.date().isoformat() == "2026-08-28"]
    pre_19 = [s for s in scenes if s.rel_orbit == 19 and s.datetime < EVENT]
    with pytest.raises(NoValidPair) as ei:
        select_pairs(post + pre_19, EVENT)
    msg = str(ei.value)
    assert "85 ascending" in msg and "19 descending" in msg
    assert "2026-09-09" in msg   # 85A last pass 08-28 + 12 d
    assert "2026-09-05" in msg   # 19D last pass 08-24 + 12 d


def test_scene_without_vh_is_rejected(scenes):
    no_vh = [dataclasses.replace(s, pols=("VV",)) if s.rel_orbit == 85 else s for s in scenes]
    best = select_pairs(no_vh, EVENT)[0]
    assert best["rel_orbit"] != 85


def test_scene_without_vh_is_rejected_from_items(items):
    its = copy.deepcopy(items)
    for it in its:
        if it["properties"]["sat:relative_orbit"] == 85:
            it["properties"]["sar:polarizations"] = ["VV"]
    best = select_pairs(scenes_from_items(its, AOI_ALL_TRACKS), EVENT)[0]
    assert best["rel_orbit"] != 85


def test_low_coverage_is_rejected(scenes):
    low = [dataclasses.replace(s, coverage=0.5) if s.rel_orbit == 85 else s for s in scenes]
    assert select_pairs(low, EVENT)[0]["rel_orbit"] != 85


def test_coverage_rejects_121d_on_trishuli_north(items):
    sc = scenes_from_items(items, TRISHULI_NORTH)
    cov = {s.rel_orbit: round(s.coverage, 2) for s in sc}
    assert cov[85] == 1.0 and cov[19] == 1.0 and cov[121] < 0.8
    best = select_pairs(sc, utc("2026-08-28T13:00:00Z"))[0]
    assert (best["rel_orbit"], best["post"].datetime.date().isoformat()) == (19, "2026-09-05")


def test_allow_cross_track_flags_pair(scenes):
    pairs = select_pairs(scenes, EVENT, allow_cross_track=True)
    best = pairs[0]
    assert best["cross_track"] is True and all(c["cross_track"] for c in pairs)
    assert (best["post"].rel_orbit, best["post"].datetime.date().isoformat()) == (85, "2026-08-28")
    assert {(p.rel_orbit, p.direction) for p in best["pre"]} == {(19, "descending")}
    assert best["pre"][0].datetime.date().isoformat() == "2026-08-24"


def test_times_fall_back_to_item_id(items):
    its = copy.deepcopy(items[:1])
    for k in ("start_datetime", "end_datetime"):
        its[0]["properties"].pop(k)
    s = scenes_from_items(its, AOI_ALL_TRACKS)[0]
    assert s.start == datetime(2026, 9, 9, 12, 21, 41, tzinfo=timezone.utc)
    assert s.end == datetime(2026, 9, 9, 12, 22, 6, tzinfo=timezone.utc)


def test_duplicate_product_stem_is_deduped(items):
    dup = copy.deepcopy(items[0])
    dup["id"] = dup["id"].replace("_3DCC_COG", "_ABCD_COG")
    dup["properties"]["processing:datetime"] = "2026-09-10T00:00:00Z"
    sc = scenes_from_items(items + [dup], AOI_ALL_TRACKS)
    assert len(sc) == 16
    assert any(s.id == dup["id"] for s in sc)   # the newer processing wins


def test_max_pre_and_window(scenes):
    best = select_pairs(scenes, EVENT, max_pre=1)[0]
    assert len(best["pre"]) == 1
    best = select_pairs(scenes, EVENT, pre_window_days=23)[0]
    assert [p.datetime.date().isoformat() for p in best["pre"]] == ["2026-08-16", "2026-08-04"]
    with pytest.raises(NoValidPair):
        select_pairs(scenes, EVENT, post_window_days=1)
    assert isinstance(best["post"], Scene)
    assert EVENT - timedelta(days=23) <= best["pre"][-1].datetime


@pytest.mark.network
def test_live_search_matches_fixture(items):
    from cutoff.data.cdse import search_s1

    live = search_s1((85.2, 28.0, 85.5, 28.3), utc("2026-07-10T00:00:00Z"), utc("2026-09-10T23:59:59Z"),
                     "https://stac.dataspace.copernicus.eu/v1")
    assert {s.id for s in live} >= {it["id"] for it in items}

"""Same-track Sentinel-1 pre/post selection (Owner: P1, task P1.1).

Rules (docs/plan/01_P1_data_sar.md P1.1, decisions D3/D4):
  - a post scene is strictly AFTER the event datetime and within `post_window_days`;
  - pre scenes are strictly before the event, within `pre_window_days`, on the SAME
    (relative orbit, orbit direction) as the post scene, newest first, at most `max_pre`;
  - scenes without VV+VH or with AOI coverage < `min_coverage` are rejected;
  - ranking: earliest post, then coverage, then number of pre scenes.
`allow_cross_track=True` is for experiment E5 only: it returns pairs whose pre scenes come from a
different track than the post scene (newest pre first), flagged `"cross_track": True`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from cutoff.data.cdse import Scene, iso

REPEAT_DAYS = 12  # single-satellite repeat cycle (only S1D over Trishuli, Jul-Sep 2026)
__all__ = ["Scene", "NoValidPair", "select_pairs", "pair_to_json"]


class NoValidPair(Exception):
    """No same-track pre/post set exists for this AOI and event."""


def _usable(s: Scene, min_coverage: float, require_pols=("VV", "VH")) -> bool:
    return all(p in s.pols for p in require_pols) and s.coverage >= min_coverage


def _track(s: Scene) -> tuple[int, str]:
    return (s.rel_orbit, s.direction)


def _no_pair_message(scenes: list[Scene], event: datetime, reason: str) -> str:
    by_track: dict[tuple[int, str], list[Scene]] = defaultdict(list)
    for s in scenes:
        by_track[_track(s)].append(s)
    if not by_track:
        return f"No Sentinel-1 scene found for this AOI around the event {iso(event)} ({reason})."
    lines = []
    for (orbit, direction), ss in sorted(by_track.items()):
        last = max(x.datetime for x in ss)
        lines.append(f"track {orbit} {direction}: {len(ss)} scene(s), last pass {iso(last)}, "
                     f"next expected pass ~{iso(last + timedelta(days=REPEAT_DAYS))}")
    return (f"No same-track Sentinel-1 pre/post set for event {iso(event)} ({reason}). Tracks seen:\n  "
            + "\n  ".join(lines))


def select_pairs(scenes, event: datetime, max_pre=3, pre_window_days=48, post_window_days=12,
                 min_coverage=0.8, allow_cross_track=False) -> list[dict]:
    """Candidate pre/post sets, best first. Each dict: rel_orbit, direction, post (Scene), pre [Scene,
    newest first], post_lag_hours, coverage (min over the set), n_pre, cross_track.
    Raises NoValidPair (listing tracks seen and the next expected pass) when there is no candidate."""
    scenes = list(scenes)
    usable = [s for s in scenes if _usable(s, min_coverage)]
    pre_lo = event - timedelta(days=pre_window_days)
    post_hi = event + timedelta(days=post_window_days)
    posts = [s for s in usable if event < s.datetime <= post_hi]
    pres = [s for s in usable if pre_lo <= s.datetime < event]

    cands = []
    for post in posts:
        if allow_cross_track:
            groups = defaultdict(list)
            for p in pres:
                if _track(p) != _track(post):
                    groups[_track(p)].append(p)
            pre_sets = list(groups.values())
        else:
            pre_sets = [[p for p in pres if _track(p) == _track(post)]]
        for pre in pre_sets:
            pre = sorted(pre, key=lambda s: s.datetime, reverse=True)[:max_pre]
            if not pre:
                continue
            cands.append({
                "rel_orbit": post.rel_orbit, "direction": post.direction, "post": post, "pre": pre,
                "post_lag_hours": (post.datetime - event).total_seconds() / 3600.0,
                "coverage": min(s.coverage for s in [post] + pre), "n_pre": len(pre),
                "cross_track": bool(allow_cross_track),
            })
    if not cands:
        reason = "cross-track pairs are not allowed" if posts and pres else (
            "no usable post-event scene" if not posts else "no usable pre-event scene")
        raise NoValidPair(_no_pair_message(scenes, event, reason))
    # earliest post, then coverage, then number of pre scenes (E5: then the newest pre scene)
    cands.sort(key=lambda c: (c["post"].datetime, -c["coverage"], -c["n_pre"],
                              -c["pre"][0].datetime.timestamp()))
    return cands


def pair_to_json(pair: dict) -> dict:
    """JSON-safe form of a select_pairs() candidate (pairs.json)."""
    out = {k: v for k, v in pair.items() if k not in ("post", "pre")}
    out["post"] = pair["post"].summary()
    out["pre"] = [p.summary() for p in pair["pre"]]
    out["post_lag_hours"] = round(pair["post_lag_hours"], 3)
    out["coverage"] = round(pair["coverage"], 4)
    return out

"""Stage `s1`: search CDSE STAC, pick a same-track pair, acquire calibrated sigma0 on the run grid.

Owner: P1 (task P1.4). Steps:
  1. search (event - 48 d -> event + 12 d), select_pairs, write pairs.json (all candidates + chosen);
  2. backend from ctx.mode (fast -> sentinelhub, full -> snap, cached -> cache only);
  3. fetch post + pre scenes (each cached at <cache_dir>/s1/<scene.id>/<grid_hash>.tif);
  4. dataMask = 0 -> NaN;  5. lee_sigma per scene per band (SNAP output is already Lee-Sigma filtered);
  6. pre-mean = NaN-aware LINEAR mean;  7. write s1_pre_mean, s1_post, lia (post scene);
  8. shadow_layover = (LIA <= 0) | (LIA >= 90) on valid pixels;  9. return the 05_contracts.md section 4 dict.
`cached` mode reads only the cache (the STAC search result is cached too) and raises CacheMiss otherwise.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Callable

import numpy as np

from cutoff.data.cdse import Scene, iso, scenes_from_items, search_items
from cutoff.data.s1_pairs import NoValidPair, pair_to_json, select_pairs
from cutoff.geo.grid import Grid
from cutoff.runctx import RunContext

STAGE = "s1"
MIN_VALID_FRACTION = 0.8
# Upper bound the frozen contract validator accepts for linear sigma0 (contracts_check: "> 50 = dB written by
# mistake"). Real ellipsoid sigma0 on slopes facing the radar exceeds it (Trishuli 2026-08-16: VV up to 113.7 on
# 20 of 2.98 M px), so values are clipped here AFTER speckle filtering and the pre-mean. This changes no downstream
# number: geo.sar.to_db caps at DB_CEIL = 5 dB (3.16 linear) and a clipped pixel stays >= 50 / 3 in any pre-mean.
LINEAR_MAX = 50.0


class CacheMiss(RuntimeError):
    """`cached` mode found no cached input for this AOI / scene."""


def grid_hash(grid: Grid) -> str:
    """Short stable id of a grid (CRS, transform, shape) used in cache paths."""
    key = json.dumps({"epsg": grid.epsg, "transform": [round(v, 6) for v in grid.transform],
                      "width": grid.width, "height": grid.height}, sort_keys=True)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def _tmp_path(path: Path) -> Path:
    """Per-process temp name next to `path` (written, then atomically renamed). A shared name let two overlapping
    runs collide on Windows ('Permission denied' deleting <hash>.snap.tmp.tif, 2026-10-13)."""
    return path.with_name(f"{path.name}.{os.getpid()}.tmp")


def cache_root(ctx: RunContext) -> Path:
    return Path(ctx.cfg.get("run", {}).get("cache_dir", "cache/"))


# --------------------------------------------------------------------------- backends
def _fetch_sentinelhub(scene: Scene, grid: Grid, ctx: RunContext) -> np.ndarray:
    from cutoff.data.sentinelhub import fetch_s1_scene

    return fetch_s1_scene(scene, grid, ctx.cfg, log=lambda **f: ctx.log(STAGE, **f))


def _fetch_snap(scene: Scene, grid: Grid, ctx: RunContext) -> np.ndarray:
    from cutoff.data.snap import fetch_s1_scene_snap

    return fetch_s1_scene_snap(scene, grid, ctx.cfg, log=lambda **f: ctx.log(STAGE, **f))


# backend(scene, grid, ctx) -> (4, H, W) float32: VV, VH linear sigma0, LIA deg, dataMask 0/1
BACKENDS: dict[str, Callable[[Scene, Grid, RunContext], np.ndarray]] = {
    "sentinelhub": _fetch_sentinelhub, "snap": _fetch_snap}
PREFILTERED = {"snap"}  # SNAP applies Lee Sigma in the graph, so geo/speckle.lee_sigma is skipped


def _scene_cache_path(ctx: RunContext, scene: Scene, backend: str) -> Path:
    suffix = "" if backend == "sentinelhub" else f".{backend}"
    return cache_root(ctx) / "s1" / scene.id / f"{grid_hash(ctx.grid)}{suffix}.tif"


def _read_cached(path: Path) -> tuple[np.ndarray, str]:
    import rasterio

    with rasterio.open(path) as ds:
        return ds.read().astype(np.float32), ds.tags().get("backend", "sentinelhub")


def _write_cached(path: Path, arr: np.ndarray, grid: Grid, backend: str, scene: Scene) -> None:
    import rasterio

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp_path(path)
    with rasterio.open(tmp, "w", **grid.profile("float32", 4, np.nan)) as dst:
        dst.write(arr.astype(np.float32))
        dst.update_tags(backend=backend, scene=scene.id, bands="VV,VH,LIA,dataMask")
        for i, name in enumerate(("VV", "VH", "LIA", "dataMask"), start=1):
            dst.set_band_description(i, name)
    tmp.replace(path)


def _check_linear(arr: np.ndarray, scene: Scene) -> None:
    """dB detector: linear sigma0 is never negative, dB almost always is. Bright (> LINEAR_MAX) values are real."""
    vals = arr[:2][np.isfinite(arr[:2]) & (arr[3][None] > 0)]
    if vals.size and vals.min() < 0:
        raise ValueError(f"{scene.id}: backend returned values {vals.min():.3g}..{vals.max():.3g}; "
                         "expected linear sigma0 (dB is never written)")


def get_scene(ctx: RunContext, scene: Scene, backend: str) -> tuple[np.ndarray, str]:
    """(4, H, W) VV, VH, LIA, dataMask for a scene on the run grid, and the backend that produced it."""
    if backend == "cached":
        for b in ("sentinelhub", "snap"):
            p = _scene_cache_path(ctx, scene, b)
            if p.exists():
                return _read_cached(p)
        raise CacheMiss(f"cached mode: scene {scene.id} is not in the cache for this grid "
                        f"({_scene_cache_path(ctx, scene, 'sentinelhub')}); run scripts/cache_aoi.py first")
    path = _scene_cache_path(ctx, scene, backend)
    if path.exists():
        ctx.log(STAGE, event="cache_hit", scene=scene.id, path=str(path))
        return _read_cached(path)
    arr = np.asarray(BACKENDS[backend](scene, ctx.grid, ctx), dtype=np.float32)
    if arr.shape != (4, ctx.grid.height, ctx.grid.width):
        raise ValueError(f"backend {backend} returned {arr.shape}, expected (4, {ctx.grid.height}, {ctx.grid.width})")
    _check_linear(arr, scene)  # before caching: bad data must never reach the cache
    _write_cached(path, arr, ctx.grid, backend, scene)
    return arr, backend


# --------------------------------------------------------------------------- search
def _search_key(bbox, start, end) -> str:
    return hashlib.sha1(json.dumps([[round(v, 6) for v in bbox], iso(start), iso(end)]).encode()).hexdigest()[:12]


def _items(ctx: RunContext, start, end) -> list[dict]:
    s1 = ctx.cfg["s1"]
    path = cache_root(ctx) / "s1" / "stac" / f"{_search_key(ctx.aoi_bbox, start, end)}.json"
    if ctx.mode == "cached":
        if not path.exists():
            raise CacheMiss(f"cached mode: no cached STAC search for this AOI/event ({path}); "
                            "run scripts/cache_aoi.py first")
        return json.loads(path.read_text(encoding="utf-8"))
    items = search_items(ctx.aoi_bbox, start, end, s1["stac_url"], collection=s1.get("collection", "sentinel-1-grd"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items), encoding="utf-8")
    return items


# --------------------------------------------------------------------------- stage
def _prepare(arr: np.ndarray, filtered: bool, spk: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """-> (2, H, W) speckle-filtered linear VV/VH, (H, W) LIA, (H, W) bool valid; dataMask = 0 -> NaN."""
    from cutoff.geo.speckle import lee_sigma

    valid = (arr[3] > 0) & np.isfinite(arr[0]) & np.isfinite(arr[1])
    sar = np.where(valid[None], arr[:2], np.nan).astype(np.float32)
    if not filtered:
        kw = {k: spk[k] for k in ("window", "target", "sigma") if k in spk}
        sar = np.stack([lee_sigma(b, looks=float(spk.get("looks", 4.4)), **kw) for b in sar])
    lia = np.where(valid, arr[2], np.nan).astype(np.float32)
    return sar, lia, valid


def stage_s1(ctx: RunContext) -> dict:
    """Writes: pairs.json, s1_pre_mean.tif, s1_post.tif, lia.tif, shadow_layover.tif.

    Returns (copied into results.inputs by the pipeline):
      {"s1_backend": "sentinelhub"|"snap"|"cached", "rel_orbit": int,
       "orbit_direction": "ascending"|"descending",
       "s1_post": {"id", "datetime", "platform"}, "s1_pre": [{"id", "datetime", "platform"}, ...],
       "post_lag_hours": float}
    Raises cutoff.data.s1_pairs.NoValidPair when no same-track pre/post set exists (never cross-track).
    """
    from cutoff.geo import raster_io
    from cutoff.geo.sar import pre_mean_linear

    s1 = ctx.cfg["s1"]
    event = ctx.event_datetime
    pre_days, post_days = int(s1.get("pre_window_days", 48)), int(s1.get("post_window_days", 12))
    start, end = event - timedelta(days=pre_days), event + timedelta(days=post_days)
    backend = s1.get("backend_for_mode", {}).get(ctx.mode, ctx.mode)
    allow_cross = bool(s1.get("allow_cross_track", False))

    # 1. search + pair selection
    scenes = scenes_from_items(_items(ctx, start, end), ctx.aoi_bbox)
    record = {"event": iso(event), "aoi_bbox": list(ctx.aoi_bbox), "search": {"start": iso(start), "end": iso(end),
              "stac_url": s1["stac_url"], "n_scenes": len(scenes)}, "scenes": [s.summary() for s in scenes],
              "rules": {"max_pre": s1.get("max_pre", 3), "min_coverage": s1.get("min_coverage", 0.8),
                        "allow_cross_track": allow_cross}, "backend": backend}
    try:
        pairs = select_pairs(scenes, event, max_pre=int(s1.get("max_pre", 3)), pre_window_days=pre_days,
                             post_window_days=post_days, min_coverage=float(s1.get("min_coverage", 0.8)),
                             allow_cross_track=allow_cross)
    except NoValidPair as e:
        record.update(candidates=[], chosen=None, error=str(e))
        ctx.path("pairs").write_text(json.dumps(record, indent=1), encoding="utf-8")
        ctx.log(STAGE, level="error", message=str(e))
        raise
    chosen = pairs[0]
    record.update(candidates=[pair_to_json(p) for p in pairs], chosen=pair_to_json(chosen))
    ctx.path("pairs").write_text(json.dumps(record, indent=1), encoding="utf-8")
    if chosen["cross_track"]:
        ctx.warn(STAGE, "Sentinel-1: CROSS-TRACK pre/post pair (experiment E5 only) - change detection is biased")
    ctx.log(STAGE, event="pair", rel_orbit=chosen["rel_orbit"], direction=chosen["direction"],
            post=chosen["post"].id, pre=[p.id for p in chosen["pre"]], backend=backend,
            post_lag_hours=round(chosen["post_lag_hours"], 2))

    # 2-5. fetch, mask, speckle filter
    spk = s1.get("speckle", {})
    prepared, used = [], set()
    for scene in [chosen["post"]] + chosen["pre"]:
        arr, src = get_scene(ctx, scene, backend)
        _check_linear(arr, scene)  # also guards arrays read back from the cache
        used.add(src)
        prepared.append(_prepare(arr, src in PREFILTERED, spk))
    (post, lia, post_valid), pres = prepared[0], prepared[1:]

    # 6. pre-mean in linear units
    pre_mean = pre_mean_linear(np.stack([p[0] for p in pres]))

    # 7-8. write
    lo, hi = s1.get("shadow_layover_lia_deg", [0, 90])
    lia_ok = post_valid & np.isfinite(lia)
    shadow = (lia_ok & ((lia <= lo) | (lia >= hi))).astype(np.uint8)
    tags = {"units": "linear sigma0", "backend": "+".join(sorted(used)), "post": chosen["post"].id}
    clipped = {"post": int((post > LINEAR_MAX).sum()), "pre_mean": int((pre_mean > LINEAR_MAX).sum())}
    post, pre_mean = np.minimum(post, LINEAR_MAX), np.minimum(pre_mean, LINEAR_MAX)  # NaN stays NaN
    tags = tags | {"clipped_at": LINEAR_MAX}
    raster_io.write(ctx, "s1_post", post, tags=tags | {"clipped_px": clipped["post"]})
    raster_io.write(ctx, "s1_pre_mean", pre_mean, tags=tags | {"pre": ",".join(p.id for p in chosen["pre"]),
                                                               "clipped_px": clipped["pre_mean"]})
    raster_io.write(ctx, "lia", lia, tags={"scene": chosen["post"].id})
    raster_io.write(ctx, "shadow_layover", shadow)

    # coverage check
    f_post = float(np.isfinite(post).all(axis=0).mean())
    f_pre = float(np.isfinite(pre_mean).all(axis=0).mean())
    for name, f in (("post", f_post), ("pre-mean", f_pre)):
        if f < MIN_VALID_FRACTION:
            ctx.warn(STAGE, f"Sentinel-1 {name}: only {100 * f:.1f}% of the grid is valid (< 80%)")
    ctx.log(STAGE, event="written", valid_post=round(f_post, 4), valid_pre_mean=round(f_pre, 4), clipped_px=clipped,
            shadow_layover_fraction=round(float(shadow.mean()), 4), backend_used=sorted(used))

    brief = lambda s: {"id": s.id, "datetime": iso(s.datetime), "platform": s.platform}
    return {"s1_backend": "cached" if ctx.mode == "cached" else backend,
            "rel_orbit": int(chosen["rel_orbit"]), "orbit_direction": chosen["direction"],
            "s1_post": brief(chosen["post"]), "s1_pre": [brief(p) for p in chosen["pre"]],
            "post_lag_hours": round(float(chosen["post_lag_hours"]), 3)}

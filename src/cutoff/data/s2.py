"""Stage `s2`: optional Sentinel-2 L2A evidence (MNDWI water + clear-sky mask) near the S1 post date.

Owner: P1 (task P1.6). Candidates: STAC `sentinel-2-l2a` within +-5 days of the S1 post scene and after the
event (`s2.require_after_event`, default true); the date with the most clear AOI pixels wins (cheap 20 m SCL probe), then B03, B11 and SCL are fetched
on the grid through the Process API (reflectance, no manual offset). clear = SCL in {4, 5, 6, 7} (snow, 11,
excluded: D11); water = clear & MNDWI = (B03 - B11) / (B03 + B11) > 0; 255 outside the data mask.
The stage never fails the run: no / cloudy / unreachable data -> no files, a warning, empty return.
"""
from __future__ import annotations

import json

import numpy as np

from cutoff.data.cdse import parse_dt
from cutoff.runctx import RunContext

STAGE = "s2"
EMPTY = {"s2_scenes": [], "s2_clear_fraction": None}


def s2_layers(b03, b11, scl, data_mask, clear_scl=(4, 5, 6, 7), mndwi_threshold: float = 0.0
              ) -> tuple[np.ndarray, np.ndarray, float]:
    """(water uint8, clear uint8, clear fraction of the grid); both layers are 255 outside the data mask."""
    b03, b11 = np.asarray(b03, np.float64), np.asarray(b11, np.float64)
    dm = (np.asarray(data_mask) > 0) & np.isfinite(b03) & np.isfinite(b11) & np.isfinite(scl)
    clear = dm & np.isin(np.asarray(scl), np.asarray(clear_scl))
    with np.errstate(divide="ignore", invalid="ignore"):
        mndwi = (b03 - b11) / (b03 + b11)
    water = clear & np.isfinite(mndwi) & (mndwi > mndwi_threshold)
    out_w = np.where(dm, water, 255).astype(np.uint8)
    out_c = np.where(dm, clear, 255).astype(np.uint8)
    return out_w, out_c, float(clear.sum()) / clear.size


def _cache_paths(ctx: RunContext, post_id: str, after_event: bool = True):
    from cutoff.data.s1_acquire import cache_root, grid_hash

    d = cache_root(ctx) / "s2" / grid_hash(ctx.grid)
    stem = post_id if after_event else f"{post_id}.any_date"  # the date rule changes the selection
    return d / f"{stem}.tif", d / f"{stem}.json"


def _get(ctx: RunContext, around, days: int, post_id: str):
    """(arr, scene ids str) | None, through the cache; cached mode never fetches."""
    import rasterio

    from cutoff.data import sentinelhub as sh

    require_after = bool(ctx.cfg.get("s2", {}).get("require_after_event", True))
    tif, meta = _cache_paths(ctx, post_id, require_after)
    if meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("scenes") is None:
            return None
        with rasterio.open(tif) as ds:
            return ds.read().astype(np.float32), m["scenes"]
    if ctx.mode == "cached":
        raise FileNotFoundError(f"cached mode: no Sentinel-2 cache for this grid ({meta})")
    got = sh.fetch_s2_best(ctx.grid, around, days, ctx.cfg, after=ctx.event_datetime if require_after else None,
                           log=lambda **f: ctx.log(STAGE, **f))
    meta.parent.mkdir(parents=True, exist_ok=True)
    if got is None:
        meta.write_text(json.dumps({"scenes": None}), encoding="utf-8")
        return None
    arr, scenes = got
    with rasterio.open(tif, "w", **ctx.grid.profile("float32", 4, np.nan)) as dst:
        dst.write(np.asarray(arr, np.float32))
        dst.update_tags(bands="B03,B11,SCL,dataMask", scenes=scenes)
    meta.write_text(json.dumps({"scenes": scenes}), encoding="utf-8")
    return np.asarray(arr, np.float32), scenes


def stage_s2(ctx: RunContext) -> dict:
    """Writes (only if a usable scene exists): s2_water.tif, s2_clear.tif.

    Returns: {"s2_scenes": [str, ...], "s2_clear_fraction": float | None}
    Must NEVER fail the run: no scene / all cloud -> return {"s2_scenes": [], "s2_clear_fraction": None}
    and ctx.warn(...).
    """
    from cutoff.geo import raster_io

    s2 = ctx.cfg.get("s2", {})
    days = int(s2.get("max_days_from_s1", 5))
    no_scene = f"Sentinel-2: no clear scene within ±{days} days"
    if not s2.get("enabled", True):
        ctx.log(STAGE, event="disabled")
        return dict(EMPTY)
    try:
        post = json.loads(ctx.path("pairs").read_text(encoding="utf-8"))["chosen"]["post"]
        around = parse_dt(post["datetime"])
        got = _get(ctx, around, days, post.get("id", around.strftime("%Y%m%dT%H%M%S")))
    except Exception as e:  # noqa: BLE001 - optional evidence: report, never fail the run
        ctx.warn(STAGE, f"Sentinel-2 skipped: {type(e).__name__}: {e}")
        return dict(EMPTY)
    if got is None:
        ctx.warn(STAGE, no_scene)
        return dict(EMPTY)
    arr, scenes = got
    water, clear, frac = s2_layers(arr[0], arr[1], arr[2], arr[3], clear_scl=tuple(s2.get("clear_scl", (4, 5, 6, 7))),
                                   mndwi_threshold=float(s2.get("mndwi_threshold", 0.0)))
    ctx.log(STAGE, event="best_scene", scenes=scenes, clear_fraction=round(frac, 4),
            window_days=days, around=post["datetime"])
    if frac < float(s2.get("min_clear_fraction", 0.10)):
        ctx.warn(STAGE, no_scene)
        return dict(EMPTY)
    raster_io.write(ctx, "s2_water", water, tags={"scenes": scenes, "rule": "clear & MNDWI > 0"})
    raster_io.write(ctx, "s2_clear", clear, tags={"scenes": scenes, "clear_scl": s2.get("clear_scl")})
    return {"s2_scenes": scenes.split(","), "s2_clear_fraction": round(frac, 4)}


__all__ = ["stage_s2", "s2_layers"]

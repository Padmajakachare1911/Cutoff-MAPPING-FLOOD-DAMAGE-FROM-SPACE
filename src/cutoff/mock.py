"""Synthetic run folder that satisfies every contract (Phase 0).

`make_mock_run(out_dir)` writes a complete, contract-valid outputs/<run_id>/ folder for
a small synthetic valley near Syapru Besi. It lets all four streams build and test
against realistic files from hour 0: P4 builds the dashboard/sitrep on it, P3 tests
exposure/network against its hazard, P2 tests gating against its terrain, P1 checks
that its real outputs look like the mock ones. The numbers are fake (model_version="mock").

    python -m cutoff.mock outputs/demo_mock
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cutoff.contracts import (ATTRIBUTION, DEFAULT_OSM_SNAPSHOT, SCENARIOS, Flag, HazardClass,
                              HAZARD_CLASS_NAMES, OTHER_FILES, RASTERS, VECTORS)
from cutoff.geo.grid import Grid, make_grid

MOCK_BBOX = (85.32, 28.14, 85.36, 28.18)


def _write(path: Path, grid: Grid, arr: np.ndarray, dtype: str, nodata=None) -> None:
    import rasterio

    arr = arr if arr.ndim == 3 else arr[None]
    with rasterio.open(path, "w", **grid.profile(dtype, arr.shape[0], nodata)) as dst:
        dst.write(arr.astype(dtype))


def _pix_to_xy(grid: Grid, col: float, row: float) -> tuple[float, float]:
    a = grid.affine
    return (a.c + (col + 0.5) * a.a, a.f + (row + 0.5) * a.e)  # north-up grid (b = d = 0)


def make_mock_run(out_dir: str | Path, run_id: str = "demo_mock") -> Path:
    import geopandas as gpd
    from rasterio.features import shapes
    from shapely.geometry import LineString, Point, box, shape

    from cutoff.report.schema import Results

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    grid = make_grid(MOCK_BBOX)
    grid.to_json(out / OTHER_FILES["grid"])
    H, W = grid.height, grid.width
    rng = np.random.default_rng(0)
    rows, cols = np.mgrid[0:H, 0:W]
    river = W / 2 + 30 * np.sin(rows / 60.0)
    dist_m = np.abs(cols - river) * 10.0

    # ---- terrain (P1 outputs)
    dem = (1400 + 0.4 * dist_m + 0.5 * (H - rows)).astype(np.float32)
    gy, gx = np.gradient(dem, 10.0)
    slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    hand = (0.4 * dist_m).astype(np.float32)
    flw = np.where(cols < river - 0.5, 1, np.where(cols > river + 0.5, 16, 4)).astype(np.uint8)
    flw[-1, :] = 0
    lia = (38 + np.where(cols < river, -1, 1) * slope).astype(np.float32)
    shadow = np.zeros((H, W), np.uint8)
    shadow[20:60, W - 60:W - 20] = 1
    for k, a, nd in (("dem", dem, np.nan), ("slope", slope, np.nan), ("hand", hand, np.nan),
                     ("lia", lia, np.nan)):
        _write(out / RASTERS[k][0], grid, a, "float32", nd)
    _write(out / RASTERS["flwdir"][0], grid, flw, "uint8", 247)
    _write(out / RASTERS["shadow_layover"][0], grid, shadow, "uint8")

    # ---- SAR (P1 outputs): linear sigma0 with speckle
    perm = dist_m < 15
    flood = (dist_m < 80) & (rows > 100) & (rows < 350) & ~perm
    debris = (dist_m >= 80) & (dist_m < 140) & (rows > 150) & (rows < 250)
    speck = lambda: rng.gamma(4.0, 0.25, (H, W))
    vv_pre = np.where(perm, 0.005, 0.08) * speck()
    vh_pre = np.where(perm, 0.001, 0.02) * speck()
    vv_post = np.where(perm | flood, 0.004, np.where(debris, 0.30, 0.08)) * speck()
    vh_post = np.where(perm | flood, 0.001, np.where(debris, 0.06, 0.02)) * speck()
    _write(out / RASTERS["s1_pre_mean"][0], grid, np.stack([vv_pre, vh_pre]), "float32", np.nan)
    _write(out / RASTERS["s1_post"][0], grid, np.stack([vv_post, vh_post]), "float32", np.nan)
    clear = rows < H // 2
    _write(out / RASTERS["s2_clear"][0], grid, clear.astype(np.uint8), "uint8", 255)
    _write(out / RASTERS["s2_water"][0], grid, ((flood | perm) & clear).astype(np.uint8), "uint8", 255)

    # ---- model + hazard (P2 outputs)
    p = np.zeros((3, H, W), np.float32)
    p[0] = 0.9; p[1] = 0.05; p[2] = 0.05
    p[:, perm] = np.array([0.05, 0.9, 0.05], np.float32)[:, None]
    p[:, flood] = np.array([0.1, 0.05, 0.85], np.float32)[:, None]
    disturb = np.zeros((H, W), np.int8)
    disturb[flood] = 1
    disturb[debris] = 2
    cls = np.zeros((H, W), np.uint8)
    flags = np.zeros((H, W), np.uint8)
    cls[debris] = HazardClass.RULE_INCREASE
    cls[flood] = np.where(hand[flood] <= 30, HazardClass.FLOOD_HIGH, HazardClass.FLOOD_POSSIBLE)
    cls[perm] = HazardClass.PERMANENT_WATER
    u8 = lambda *fs: np.uint8(sum(int(f) for f in fs))  # IntEnum -> uint8 (numpy won't downcast int64)
    flags[flood] |= u8(Flag.MODEL_FLOOD, Flag.RULE_DECREASE)
    flags[debris] |= u8(Flag.RULE_INCREASE)
    flags[slope > 15] |= u8(Flag.STEEP)
    flags[hand > 30] |= u8(Flag.HIGH_HAND)
    flags[shadow == 1] |= u8(Flag.SHADOW_LAYOVER)
    cls[shadow == 1] = HazardClass.NO_OBS
    disturb[shadow == 1] = -1
    p[:, shadow == 1] = np.nan
    _write(out / RASTERS["p_model"][0], grid, p, "float32", np.nan)
    _write(out / RASTERS["disturb"][0], grid, disturb, "int8")
    _write(out / RASTERS["hazard_class"][0], grid, cls, "uint8")
    _write(out / RASTERS["flags"][0], grid, flags, "uint8")

    recs = [{"geometry": shape(g), "class": int(v)}
            for g, v in shapes(cls.astype(np.int16), mask=np.isin(cls, [1, 2, 3, 4]), transform=grid.affine)]
    hz = gpd.GeoDataFrame(recs, geometry="geometry", crs=grid.crs)
    hz["area_m2"] = hz.area
    hz.to_file(out / VECTORS["hazard"][0], layer="hazard", driver="GPKG")

    # ---- OSM + derived layers (P3 outputs)
    P = lambda c, r: _pix_to_xy(grid, c, r)
    rx = lambda r: W / 2 + 30 * np.sin(r / 60.0)
    main = LineString([P(rx(r) + 12, r) for r in range(0, H, 10)])
    side = LineString([P(rx(300) + 12, 300), P(W - 30, 300)])
    left = LineString([P(rx(200) - 15, 200), P(30, 200)])
    bridge = LineString([P(rx(200) - 15, 200), P(rx(200) + 12, 200)])
    roads = gpd.GeoDataFrame({
        "osm_id": ["way/1", "way/2", "way/3", "way/4"],
        "highway": ["primary", "tertiary", "unclassified", "unclassified"],
        "tier": ["road", "road", "road", "road"],
        "bridge": [False, False, False, True],
        "name": ["Pasang Lhamu Hwy (mock)", "", "", "Mock bridge"],
    }, geometry=[main, side, left, bridge], crs=grid.crs)
    roads.to_file(out / VECTORS["osm_roads"][0], driver="GPKG")
    villages = {"Upper Village": P(rx(10) + 20, 10), "East Hamlet": P(W - 30, 305),
                "West Village": P(30, 205), "Orphan Hamlet": P(40, 40)}
    places = gpd.GeoDataFrame({"osm_id": [f"node/{i}" for i in range(4)], "place": ["village", "hamlet", "village", "hamlet"],
                               "name": list(villages)}, geometry=[Point(v) for v in villages.values()], crs=grid.crs)
    places.to_file(out / VECTORS["osm_places"][0], driver="GPKG")
    blds = []
    for (x, y) in villages.values():
        for dx in (-30, 0, 30):
            blds.append(box(x + dx - 6, y - 6, x + dx + 6, y + 6))
    for r in (180, 220, 260):  # houses beside the river inside the flood
        x, y = P(rx(r) + 5, r)
        blds.append(box(x - 6, y - 6, x + 6, y + 6))
    buildings = gpd.GeoDataFrame({"osm_id": [f"way/{100 + i}" for i in range(len(blds))]}, geometry=blds, crs=grid.crs)
    buildings.to_file(out / VECTORS["osm_buildings"][0], driver="GPKG")
    hosp = P(rx(H - 5) + 20, H - 5)
    health = gpd.GeoDataFrame({"osm_id": ["node/99"], "kind": ["hospital"], "name": ["District Hospital (mock)"]},
                              geometry=[Point(hosp)], crs=grid.crs)
    health.to_file(out / VECTORS["osm_health"][0], driver="GPKG")
    sett = gpd.GeoDataFrame({"sid": [f"S{i}" for i in range(4)], "name": list(villages),
                             "source": ["osm_place"] * 4, "n_buildings": [3, 3, 3, 3]},
                            geometry=[Point(v) for v in villages.values()], crs=grid.crs)
    sett.to_file(out / VECTORS["settlements"][0], driver="GPKG")
    targets = gpd.GeoDataFrame({"tid": ["T0"], "name": ["District Hospital (mock)"], "kind": ["hospital"]},
                               geometry=[Point(hosp)], crs=grid.crs)
    targets.to_file(out / VECTORS["targets"][0], driver="GPKG")

    hz_union = hz[hz["class"].isin([1, 2, 3, 4])].union_all()
    exb = buildings[buildings.intersects(hz_union)].copy()
    exb["hazard_class"] = 1
    exb.to_file(out / VECTORS["exposure_buildings"][0], driver="GPKG")
    exr = roads.copy()
    exr["geometry"] = roads.intersection(hz_union)
    exr = exr[~exr.is_empty].copy()
    exr["hazard_class"] = 1
    exr["length_m"] = exr.length
    exr[["osm_id", "hazard_class", "length_m", "geometry"]].to_file(out / VECTORS["exposure_roads"][0], driver="GPKG")

    statuses = {  # fake but plausible per scenario
        "A": ["cut_off", "connected", "cut_off", "unknown"],
        "B": ["cut_off", "connected", "connected", "unknown"],
        "C": ["connected", "connected", "cut_off", "unknown"],
    }
    access = []
    for s, st in statuses.items():
        g = sett.copy()
        g["status"] = st
        g["t0_min"] = [22.0, 9.0, 31.0, np.nan]
        g["t1_min"] = [np.inf if x == "cut_off" else (np.nan if x == "unknown" else t)
                       for x, t in zip(st, [22.0, 9.0, 31.0, np.nan])]
        g.to_file(out / VECTORS[f"settlements_{s}"][0], driver="GPKG")
        rs = roads.copy()
        rs["seg_id"] = range(len(rs))
        rs["closed"] = [s == "A", False, False, s in ("A", "C")]
        rs[["seg_id", "closed", "bridge", "geometry"]].to_file(out / VECTORS[f"roads_{s}"][0], driver="GPKG")
        ll = g.to_crs(4326)
        ref = lambda status: [{"sid": r.sid, "name": r["name"], "lon": r.geometry.x, "lat": r.geometry.y,
                               "t0_min": None if np.isnan(r.t0_min) else r.t0_min}
                              for _, r in ll[ll.status == status].iterrows()]
        access.append({"scenario": s, "description": SCENARIOS[s],
                       "closed_road_km": round(float(rs[rs.closed].length.sum()) / 1000, 2),
                       "closed_bridges": int((rs.closed & rs.bridge).sum()),
                       "counts": {k: st.count(k) for k in ("connected", "degraded", "cut_off", "unknown")},
                       "cut_off": ref("cut_off"), "degraded": ref("degraded")})

    px_km2 = 100.0 / 1e6
    areas = {HAZARD_CLASS_NAMES[c]: round(float((cls == c).sum()) * px_km2, 4) for c in (1, 2, 3, 4, 5)}
    ev = datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc)
    res = Results(
        run_id=run_id, created_utc=datetime.now(timezone.utc), model_version="mock",
        inputs={
            "aoi_bbox": MOCK_BBOX, "grid_epsg": grid.epsg, "event_datetime": ev,
            "osm_snapshot": DEFAULT_OSM_SNAPSHOT, "mode": "cached", "s1_backend": "cached",
            "rel_orbit": 85, "orbit_direction": "ascending",
            "s1_post": {"id": "MOCK_S1D_20260828T122141", "datetime": "2026-08-28T12:21:41Z", "platform": "sentinel-1d"},
            "s1_pre": [{"id": "MOCK_S1D_20260816T122141", "datetime": "2026-08-16T12:21:41Z", "platform": "sentinel-1d"}],
            "post_lag_hours": 57.5, "s2_scenes": ["MOCK_S2"], "s2_clear_fraction": 0.5},
        hazard={"area_km2_by_class": areas, "no_observation_km2": round(float((cls == 254).sum()) * px_km2, 4),
                "sigma_stable_db": 1.1, "k_sigma": 3.0, "flood_threshold": 0.5, "temperature": 1.0,
                "stable_steep_fpr": 0.0},
        exposure={"buildings_by_class": {"flood_high": int(len(exb))},
                  "road_km_by_class": {"flood_high": round(float(exr.length_m.sum()) / 1000, 2)},
                  "bridges_by_class": {"flood_high": 1}},
        access=access,
        warnings=["MOCK DATA - synthetic valley, not a real observation"],
        timings_s={"mock": 0.0},
        limitations=["Synthetic mock run for development only."],
        attribution=list(ATTRIBUTION),
    )
    (out / OTHER_FILES["results"]).write_text(res.model_dump_json(indent=1), encoding="utf-8")
    (out / OTHER_FILES["pairs"]).write_text(json.dumps({"mock": True}), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(make_mock_run(sys.argv[1] if len(sys.argv) > 1 else "outputs/demo_mock"))

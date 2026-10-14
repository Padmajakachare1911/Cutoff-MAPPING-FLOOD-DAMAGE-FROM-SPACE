# Interface contracts (v1.0.0)

The code is the authority: `src/cutoff/contracts.py`, `runctx.py`, `geo/grid.py`, `report/schema.py`, `contracts_check.py`. This page explains them. If this page and the code disagree, the code wins; fix this page.

## 1. The run folder

`cutoff run` creates `outputs/<run_id>/`. The pipeline writes `grid.json` first, then calls the stages in this order, validating each stage's outputs before the next stage starts:

| # | Stage (owner) | Function | Reads | Writes |
|---|---|---|---|---|
| 1 | s1 (P1) | `cutoff.data.s1_acquire.stage_s1` | grid | `pairs.json`, `s1_pre_mean.tif`, `s1_post.tif`, `lia.tif`, `shadow_layover.tif` |
| 2 | terrain (P1) | `cutoff.data.dem.stage_terrain` | grid | `dem.tif`, `slope.tif`, `hand.tif`, `flwdir_d8.tif` |
| 3 | s2 (P1, optional) | `cutoff.data.s2.stage_s2` | pairs | `s2_water.tif`, `s2_clear.tif` (or nothing + warning) |
| 4 | model (P2) | `cutoff.ml.infer.stage_model` | s1_*, slope | `p_model.tif` |
| 5 | disturbance (P2) | `cutoff.geo.change.stage_disturbance` | s1_*, hand, shadow_layover | `disturb.tif` |
| 6 | gating (P2) | `cutoff.geo.gating.stage_gating` | p_model, disturb, slope, hand, shadow_layover, s2_* | `hazard_class.tif`, `flags.tif` |
| 7 | vectorize (P2) | `cutoff.geo.vectorize.stage_vectorize` | hazard_class | `hazard.gpkg` |
| 8 | osm (P3) | `cutoff.data.osm.stage_osm` | grid | `osm_roads/buildings/places/health.gpkg` |
| 9 | settlements (P3) | `cutoff.geo.settlements.stage_settlements` | osm_* | `settlements.gpkg`, `targets.gpkg` |
| 10 | exposure (P3) | `cutoff.geo.exposure.stage_exposure` | hazard, osm_* | `exposure_buildings.gpkg`, `exposure_roads.gpkg` |
| 11 | access (P3) | `cutoff.geo.network.stage_access` | osm_roads, hazard, settlements, targets | `settlements_{A,B,C}.gpkg`, `roads_status_{A,B,C}.gpkg` |
| 12 | report (P4) | `cutoff.report.sitrep.render` | results.json | `sitrep.html`, `sitrep.pdf` |

Bonus (P3): `cutoff.geo.flowpath.trace_flowpath(ctx, lon, lat)` → `flowpath.gpkg`, plus `results.flowpath`.

## 2. Raster rules (all of them)

- Exactly the run grid: `Grid.from_json(run_dir/"grid.json")`. Write with `rasterio.open(path, "w", **grid.profile(dtype, count, nodata))`. Never write in EPSG:4326 or 3857.
- Float no-data = NaN; integer rasters use the codes below.
- SAR is **linear σ⁰** on disk (`s1_*.tif`); dB happens only inside the model input builder (`cutoff.geo.sar`). The validator rejects negative or > 50 values as "dB written by mistake".

| File | Bands / dtype | Values |
|---|---|---|
| `s1_pre_mean.tif` | 2 × float32 | VV, VH linear σ⁰; mean of the pre scenes in **linear** units, after speckle filtering |
| `s1_post.tif` | 2 × float32 | VV, VH linear σ⁰, speckle-filtered |
| `lia.tif` | float32 | local incidence angle (degrees) of the POST scene |
| `shadow_layover.tif` | uint8 | 1 = unobservable (LIA ≤ 0 or ≥ 90, or a backend mask), 0 = ok |
| `dem.tif` | float32 | GLO-30 heights (m), bilinear to the grid |
| `slope.tif` | float32 | degrees, `np.gradient` on dem.tif at 10 m |
| `hand.tif` | float32 | m above nearest drainage (pyflwdir, streams = upstream area > 1 km²), computed on a ≥ 3 km buffered DEM then cropped |
| `flwdir_d8.tif` | uint8 | pyflwdir D8 codes (1 E, 2 SE, 4 S, 8 SW, 16 W, 32 NW, 64 N, 128 NE, 0 pit, 247 nodata) |
| `s2_water.tif` / `s2_clear.tif` | uint8 | 1/0, 255 = no S2 data. clear = SCL ∈ {4,5,6,7}; water = clear & MNDWI > 0 |
| `p_model.tif` | 3 × float32 | softmax(z/T) for no_water, permanent_water, flood; NaN where invalid; sums to 1 |
| `disturb.tif` | int8 | −1 invalid, 0 none, 1 decrease (water/smooth mud), 2 increase (roughness/debris) |
| `hazard_class.tif` | uint8 | 0 none, 1 flood high, 2 flood possible, 3 rule decrease, 4 rule increase, 5 permanent water, 254 no observation |
| `flags.tif` | uint8 | bits: 1 model flood, 2 rule decrease, 4 rule increase, 8 S2 agrees water, 16 S2 clear no water, 32 steep, 64 high HAND, 128 shadow/layover |

### Gating truth table (P2 implements, P3/P4 rely on it)

Evaluated in this order; later rules override earlier ones:

1. `disturb == 1` → 3; `disturb == 2` → 4
2. `p_flood ≥ τ` → 1
3. class 1 and (`slope > 15°` or `HAND > 30 m`) → 2
4. `p_permanent ≥ τ` and not model flood, and not (`slope > 15°` or `HAND > 30 m`) → 5 (same terrain test as rule 3; amended 2026-10-14, P2: radar back-slopes were mapped as water on Trishuli, E5)
5. S2 present: class 2 and S2 water-agree → 1; class 1 and S2 clear-no-water and not disturb==1 → 2; class 5 and S2 clear-no-water → the class from rules 1–3 (amended 2026-10-14, P2: dry desert mapped as permanent water at Deir ez-Zor)
6. shadow/layover or invalid probs or disturb == −1 → 254

## 3. Vector rules

- GeoPackage, grid CRS (UTM), one layer per file (the default layer name is fine; `hazard.gpkg` uses layer `hazard`).
- Required columns are listed in `contracts.VECTORS`. Extra columns are allowed.
- `osm_roads.tier` ∈ {`road`, `track`, `trail`}; `bridge` is bool; `highway` is the OSM value.
- `settlements.source` ∈ {`osm_place`, `building_cluster`}; `targets.kind` ∈ {`hospital`, `clinic`, `health_post`, `doctors`, `town`, `city`}.
- `settlements_{S}.status` ∈ {`connected`, `degraded`, `cut_off`, `unknown`}; `t0_min` = baseline minutes to nearest target (NaN if unknown); `t1_min` = after closures (inf if cut off).
- Any GeoJSON exported for the web is reprojected to EPSG:4326, and OSM-derived exports carry `ODBL_NOTICE`.

## 4. Stage return values → `results.json`

Each stage returns a dict; the pipeline (P4) maps it into `Results`:

| Stage | Returns | Goes to |
|---|---|---|
| s1 | `s1_backend, rel_orbit, orbit_direction, s1_post{id,datetime,platform}, s1_pre[...], post_lag_hours` | `inputs.*` |
| terrain | `dem_tiles, hand_stream_upa_km2` | run.log only |
| s2 | `s2_scenes, s2_clear_fraction` | `inputs.*` |
| model | `model_version, flood_threshold, temperature` | `model_version`, `hazard.*` |
| disturbance | `sigma_stable_db, k_sigma, n_stable_px` | `hazard.*` |
| gating | `stable_steep_fpr` | `hazard.stable_steep_fpr` |
| vectorize | `area_km2_by_class, no_observation_km2` | `hazard.*` |
| osm | `osm_snapshot, osm_api, counts` | run.log + warnings |
| settlements | `n_settlements, n_targets` | run.log |
| exposure | `buildings_by_class, road_km_by_class, bridges_by_class` | `exposure` |
| access | `access: [ScenarioResult × 3]` | `access` |

`area_km2_by_class` and the exposure dict keys use the lower-case `HazardClass` names (`flood_high`, `flood_possible`, `rule_decrease`, `rule_increase`, `permanent_water`, `no_obs`).

Backward-compatible computed JSON fields (14 October 2026):
- `hazard.total_hazard_km2`: sum of classes 1–4, rounded to four decimals;
  permanent water and no observation are excluded.
- `exposure.total_exposed_buildings`: sum of the existing exposed-building counts.
- `is_partial`: missing exposure/access or an explicit pipeline partial warning.

`Results` recomputes these fields when loading older files; old run folders remain
valid. The dashboard reads these backend totals instead of calculating new metrics.

## 5. The model checkpoint (P2 → P4)

`models/cutoff_unet_v1.pt` = `torch.save({"state_dict", "meta"})`, where meta contains at least:
`channels` (== `contracts.CHANNELS`), `contract_version`, `mean[7]`, `std[7]` (computed on train events, dB/deg units), `slope_clip`, `temperature`, `flood_threshold` (τ), `encoder`, `config_hash`, `train_events`, `val_events`, `git_commit`.
`load_checkpoint` must raise if `meta["channels"] != CHANNELS`.

## 6. CLI (P4)

```
cutoff run --bbox W,S,E,N --event 2026-08-26T02:52:00Z [--mode cached|fast|full] [--model PATH|b0]
           [--osm-snapshot 2026-07-27T00:00:00Z] [--out outputs/] [--run-id ID] [--stages s1,terrain,...]
           [--flowpath LON,LAT]
cutoff train --config configs/train_unet.yaml --seed 42          (P2)
cutoff eval-kuro --checkpoint models/cutoff_unet_v1.pt --strata slope   (P2)
```
`--event` also accepts a bare date (`2026-08-26`). It is read as the **end** of that day (23:59:59 UTC), so a same-day pass from before the event can never be treated as post-event. A warning then says that same-day post-event passes are ignored.

# P1 — Data & SAR stream (Person 1)

> **For agentic workers:** you own stages `s1`, `terrain`, `s2`. Read `00_MASTER_PLAN.md` and `05_contracts.md` first. Your outputs must pass `validate_run_dir(run_dir, keys=[...])` and must look like the mock run's files (`python -m cutoff.mock outputs/demo_mock`). TDD: write the listed test, watch it fail, implement, watch it pass, commit. One PR per task.

**You deliver:** a same-track Sentinel-1 pair for any AOI and event; calibrated, speckle-filtered linear σ⁰ (pre-mean + post) on the run grid; local incidence angle and an unobservable mask; Copernicus DEM, slope, HAND and D8 flow directions; optional Sentinel-2 water/clear evidence; cached inputs for the demo AOIs; experiments E3c and E5.

**Files you own:** `src/cutoff/data/{cdse,s1_pairs,s1_acquire,sentinelhub,snap,dem,s2}.py`, `src/cutoff/geo/{terrain,speckle}.py`, `graphs/s1_cutoff.xml`, `scripts/cache_aoi.py`, `tests/test_p1_*.py`, `tests/fixtures/stac_*.json`, `docs/results/E3c.md`, `docs/results/E5.md`.

**Consumes:** `Grid`, `RunContext`, `contracts.RASTERS` (Phase 0). **Produces for others:** the files and return dicts in `05_contracts.md` §1/§4. P2 needs `s1_*`, `slope`, `hand`, `shadow_layover`; P3 needs `flwdir_d8`/`dem` (bonus); P4 needs your return dicts.

**Verified facts you rely on (2026-10-12):**
- CDSE STAC `https://stac.dataspace.copernicus.eu/v1`, collection `sentinel-1-grd`. Item properties: `sat:relative_orbit`, `sat:orbit_state` (`ascending`/`descending`), `sar:polarizations`, `sar:instrument_mode`, `platform` (`sentinel-1c`/`sentinel-1d`), `product:type` (`IW_GRDH_1S`). Assets: `vv`, `vh` COG (uint16 DN, nodata 0), `Product` (zip), `schema-calibration-*` XML. Item ids end in `_COG`. No auth needed for search.
- Trishuli bbox 85.2–85.5E / 28.0–28.3N, Jul–Sep 2026: only Sentinel-1D, three tracks with 12-day repeats.
  - **85 ascending** at ~12:21 UTC: 07-11, 07-23, 08-04, 08-16, **08-28**, 09-09
  - **19 descending** at ~00:18 UTC: 07-19, 07-31, 08-12, 08-24, **09-05**
  - **121 descending** at ~00:10 UTC: 07-14, 07-26, 08-07, 08-19, **08-31**
- Sentinel Hub Process API on CDSE: `https://sh.dataspace.copernicus.eu/api/v1/process`; token from `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token` (client_credentials). S1 options: `backCoeff` SIGMA0_ELLIPSOID, `orthorectify` true, `demInstance` COPERNICUS_30, `speckleFilter` NONE|LEE, `resolution` HIGH = 10 m (IW). Output bands VV, VH (linear power), `localIncidenceAngle` (needs orthorectify), `dataMask`. There is **no relative-orbit filter**, so we pin each scene by its exact acquisition time window + orbit direction. A request is limited to 2500 × 2500 px, so tile larger grids.
- Kuro Siwo SNAP graph (`configs/grd_preprocessing.xml`): Apply-Orbit → Subset → ThermalNoiseRemoval → Remove-GRD-Border-Noise → Land-Sea-Mask → Calibration (σ⁰, **linear**, not dB) → Speckle **Lee Sigma** (window 7×7, target 3×3, sigma 0.9) → Terrain-Correction (SRTM 1Sec, 10 m, EPSG:3857, bilinear).
- GLO-30 public bucket (no auth): `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N28_00_E085_00_DEM/Copernicus_DSM_COG_10_N28_00_E085_00_DEM.tif` (`_10_` = 1 arc-second; the N/E name is the lower-left corner of the 1°×1° tile).
- pyflwdir: `from_dem(data, nodata=-9999., transform=Affine, latlon=False)`, `flw.upstream_area(unit="km2")`, `flw.hand(drain=bool2d, elevtn=float2d)` (nodata −9999), `flw.to_array("d8")`, `flw.path(xy=(xs, ys), direction="down", max_length=..., unit="m")`.

---

### P1.0 Setup and recon (T+0 → T+1)
- [ ] Create a CDSE account and a Sentinel Hub OAuth client; fill `.env`. Run `make test` (green).
- [ ] Record the STAC fixture: search `sentinel-1-grd`, bbox `85.2,28.0,85.5,28.3`, datetime `2026-07-10/2026-09-10`, limit 100. Save the raw item JSON list to `tests/fixtures/stac_trishuli_s1.json` (properties + geometry + asset hrefs; drop thumbnails). It must contain 16 items as listed above.
- [ ] Commit: `test: record CDSE STAC fixture for Trishuli`.

### P1.1 STAC search + same-track pair selection (T+1 → T+3)
**Files:** `src/cutoff/data/cdse.py`, `src/cutoff/data/s1_pairs.py`, `tests/test_p1_pairs.py`
**Interface:**
```python
@dataclass(frozen=True)
class Scene:
    id: str; datetime: datetime; start: datetime; end: datetime
    rel_orbit: int; direction: str; platform: str; pols: tuple[str, ...]
    coverage: float                     # fraction of the AOI covered by the item footprint (computed in UTM)
    assets: dict[str, str]              # vv, vh, Product, schema-calibration-vv, ...
class NoValidPair(Exception): ...
def search_s1(bbox, start: datetime, end: datetime, stac_url: str) -> list[Scene]
def select_pairs(scenes, event: datetime, max_pre=3, pre_window_days=48, post_window_days=12,
                 min_coverage=0.8, allow_cross_track=False) -> list[dict]
```
- [ ] Write failing tests (use the fixture through a `scenes_from_items(items, aoi)` helper so they run offline):
  - event `2026-08-26T02:52Z` → best set = rel_orbit 85, ascending, post `2026-08-28T12:21:41Z`, pre = [08-16, 08-04, 07-23] (newest first), `post_lag_hours ≈ 57.5`;
  - event `2026-08-28T13:00Z` → best post is `2026-08-31` (121 descending), never 08-28;
  - only cross-track candidates → `NoValidPair`, whose message lists the tracks seen and the next expected pass (last pass + 12 d);
  - a scene without VH is rejected; coverage < 0.8 is rejected;
  - `allow_cross_track=True` returns a pair whose dict carries `"cross_track": True` (E5 only).
- [ ] Implement it (rules: post strictly **after** the event; same `(rel_orbit, direction)`; ranking by earliest post, then coverage, then number of pre scenes). Dedupe items with the same product stem.
- [ ] `start`/`end` come from `start_datetime`/`end_datetime` if present, else the timestamps in the item id (`..._YYYYMMDDTHHMMSS_YYYYMMDDTHHMMSS_...`).
- [ ] Tests green; commit.

### P1.2 Speckle filter (T+1 → T+4, parallel with P1.1)
**Files:** `src/cutoff/geo/speckle.py`, `tests/test_p1_speckle.py`
```python
def lee_sigma(img: np.ndarray, window: int = 7, target: int = 3, sigma: float = 0.9,
              looks: float = 4.4, point_pct: float = 98.0) -> np.ndarray   # linear in, linear out, NaN-safe
```
- [ ] Implement the improved Lee sigma filter (Lee et al. 2009, IEEE TGRS 47(1)):
  1. Keep strong point targets: pixels whose 3×3 target window has ≥ k pixels above the 98th percentile stay unfiltered.
  2. Sigma range from the speckle distribution for the given looks and sigma = 0.9.
  3. MMSE estimate over the in-range pixels of the 7×7 window.

  Time box: 2 h. If you exceed it, ship a refined-Lee 7×7 (`looks` = 4.4 for IW GRDH) and record the deviation in `docs/results/E3c.md`.
- [ ] Tests:
  - flat gamma-speckled field → filtered coefficient of variation is < 40 % of the input's;
  - a step edge stays a step (the mean on each side is preserved within 5 %);
  - an isolated bright point survives;
  - NaNs stay NaN and don't spread beyond the window.

### P1.3 Sentinel Hub backend (fast mode) (T+3 → T+8)
**Files:** `src/cutoff/data/sentinelhub.py`, `tests/test_p1_sentinelhub.py`
```python
def get_token(client_id, client_secret, token_url) -> str            # cache until expiry
def fetch_s1_scene(scene: Scene, grid: Grid, cfg) -> np.ndarray        # (4, H, W) float32: VV, VH, LIA, dataMask
def fetch_s2_best(grid, around: datetime, days: int, cfg) -> tuple[np.ndarray, str] | None   # used by P1.6
```
Request body (tile the grid into ≤ 2500 px chunks aligned to the grid; the bbox is the chunk bounds in grid CRS metres):
```json
{"input": {"bounds": {"bbox": [L, B, R, T], "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/32645"}},
  "data": [{"type": "sentinel-1-grd",
    "dataFilter": {"timeRange": {"from": "<scene.start - 60 s>", "to": "<scene.end + 60 s>"},
                   "acquisitionMode": "IW", "polarization": "DV", "resolution": "HIGH",
                   "orbitDirection": "ASCENDING"},
    "processing": {"backCoeff": "SIGMA0_ELLIPSOID", "orthorectify": true,
                   "demInstance": "COPERNICUS_30", "speckleFilter": {"type": "NONE"}}}]},
 "output": {"width": W, "height": H, "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]},
 "evalscript": "//VERSION=3\nfunction setup(){return {input:[{bands:[\"VV\",\"VH\",\"localIncidenceAngle\",\"dataMask\"]}],output:{bands:4,sampleType:\"FLOAT32\"}};}\nfunction evaluatePixel(s){return [s.VV,s.VH,s.localIncidenceAngle,s.dataMask];}"}
```
- [ ] Unit test with a mocked HTTP response: a TIFF written on the chunk grid is placed into the right window of the full array; the tiling covers the grid exactly once; the request carries the right time window and orbit direction.
- [ ] `@pytest.mark.network` test: fetch the Trishuli post scene (85A, 08-28) for a 5 × 5 km chunk.
  - The response transform equals the chunk grid.
  - VV median is between 0.01 and 0.3 (linear).
  - LIA is in [0, 90] on > 90 % of pixels.
- [ ] Log processing units used per request (response header `x-processingunits-spent` if present) into run.log.

### P1.4 `stage_s1` assembling the run (T+6 → T+10) — **needed for C1**
**Files:** `src/cutoff/data/s1_acquire.py`, `scripts/cache_aoi.py`, `tests/test_p1_stage_s1.py`
- [ ] `stage_s1(ctx)`:
  1. Search (event − 48 d → event + 12 d), `select_pairs`, write `pairs.json` (all candidates + chosen).
  2. Pick the backend from `ctx.mode` (`fast` → sentinelhub, `full` → snap, `cached` → cache).
  3. Fetch post + pre scenes.
  4. Set dataMask = 0 → NaN.
  5. Apply `lee_sigma` per scene per band.
  6. Pre-mean = NaN-aware **linear** mean.
  7. Write `s1_pre_mean.tif`, `s1_post.tif`, `lia.tif` (post scene).
  8. Write `shadow_layover.tif` = (LIA ≤ 0) | (LIA ≥ 90) on valid pixels.
  9. Return the dict from `05_contracts.md` §4.
- [ ] Coverage check after fetch: if < 80 % of the grid is valid in post or pre-mean, call `ctx.warn(...)` with the percentage.
- [ ] Cache: write fetched scene arrays to `cache/s1/<scene.id>/<grid_hash>.tif` and reuse them. `cached` mode reads only the cache and raises `CacheMiss` (a clear message) if absent.
- [ ] `scripts/cache_aoi.py --name trishuli_north --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z` runs stages s1, terrain and s2 in fast mode and fills the cache.
- [ ] Tests:
  - with a fake backend (deterministic arrays) the stage writes contract-valid files (`validate_run_dir(..., keys=[s1_pre_mean, s1_post, lia, shadow_layover])`);
  - a NaN in one pre scene is filled by the other pre scene;
  - dB is never written (the validator catches it).
- [ ] Network run on Trishuli north: commit the `run.log` excerpt and a quick-look PNG (VV dB pre vs post) to `docs/plan/reports/P1.4.md`.

### P1.5 Terrain stage (T+3 → T+8) — **needed for C1**
**Files:** `src/cutoff/data/dem.py`, `src/cutoff/geo/terrain.py`, `tests/test_p1_terrain.py`
```python
def glo30_tiles(bbox_wgs84) -> list[str]                        # URLs of the 1°x1° tiles intersecting bbox
def dem_on_grid(grid: Grid, buffer_m: float = 0) -> tuple[np.ndarray, Grid]   # /vsicurl/ + WarpedVRT bilinear
def slope_degrees(dem, pixel_m) -> np.ndarray
def hand_flowdir(dem, grid) -> tuple[np.ndarray, np.ndarray]    # (hand_m float32 NaN-nodata, d8 uint8)
```
- [ ] Tests:
  - tile names for bbox (85.28, 27.95, 85.42, 28.29) = N27_00_E085_00 and N28_00_E085_00;
  - slope of a 10 % plane ≈ 5.71°;
  - on a synthetic V-valley (two planes meeting at a channel), HAND = 0 on the channel and grows linearly with distance;
  - the d8 values of a tilted plane all point downhill;
  - outputs are cropped exactly back to the run grid.
- [ ] `stage_terrain(ctx)`:
  1. Build a buffered grid (`cfg.dem.hand_buffer_m` = 3 km, same 10 m alignment) and get the DEM on it.
  2. Compute HAND and d8 there (streams = `upstream_area("km2") > 1.0`), then crop.
  3. Compute slope on the run grid.
  4. Write `dem.tif`, `slope.tif`, `hand.tif` (NaN for −9999) and `flwdir_d8.tif`.
- [ ] Check on Trishuli north: HAND < 10 m along the Bhote Koshi channel; > 100 m on the ridges. Commit a quick-look PNG to the report.
- [ ] Limitation to note in the report: GLO-30 is a surface model (trees and buildings included), and at 30 m it smooths narrow gorges, which inflates HAND near the riverbank. That is why the HAND corridor in `rules` is 60 m.

### P1.6 Sentinel-2 evidence stage (T+8 → T+14)
**Files:** `src/cutoff/data/s2.py`, `tests/test_p1_s2.py`
- [ ] List candidates with STAC collection `sentinel-2-l2a` within ±5 days of the S1 post scene; pick the date with the most clear AOI pixels (fetch SCL first, at 20 m, cheaply).
- [ ] Fetch B03, B11 and SCL on the grid via the Process API (`type: "sentinel-2-l2a"`; the evalscript returns reflectance, with no manual offset needed).
- [ ] `clear` = SCL ∈ {4, 5, 6, 7}. `water` = clear & MNDWI = (B03 − B11)/(B03 + B11) > 0. Write `s2_water.tif` and `s2_clear.tif`; set 255 outside the data mask.
- [ ] The stage never raises for missing or cloudy data: it returns `{"s2_scenes": [], "s2_clear_fraction": None}` and calls `ctx.warn("Sentinel-2: no clear scene within ±5 days")`.
- [ ] Test with synthetic SCL/bands (water, cloud, snow cases) and a no-scene case.

### P1.7 Full (SNAP) backend (T+12 → T+22)
**Files:** `src/cutoff/data/snap.py`, `graphs/s1_cutoff.xml`, `tests/test_p1_snap.py`
- [ ] Copy Kuro Siwo's `configs/grd_preprocessing.xml` (cite it in a header comment) and change four things:
  1. Subset by geoRegion = the grid's WGS84 bounds + 1 km, done first after Apply-Orbit.
  2. Remove Land-Sea-Mask.
  3. Terrain-Correction with DEM "Copernicus 30m Global DEM", map projection = the grid EPSG, 10 m, and `saveLocalIncidenceAngle=true`.
  4. Speckle filter as in Kuro Siwo (Lee Sigma 7×7, target 3×3, sigma 0.9).

  [U] Check the exact parameter names with `gpt Terrain-Correction -h` and `gpt Speckle-Filter -h`, and record them in the report.
- [ ] Download the `Product` zip via `https://download.dataspace.copernicus.eu/odata/v1/Products(<uuid>)/$value` (Bearer token), or read the COG SAFE from S3 (`s3://eodata/...`, endpoint `https://eodata.dataspace.copernicus.eu`) with your S3 keys.
- [ ] Reproject the SNAP output onto the run grid (bilinear) and feed the same writer as P1.4. Lee Sigma comes from SNAP here, so skip `lee_sigma` for this backend.
- [ ] Mark the tests `slow`/`network`. Acceptance: the Trishuli post scene processed in full mode passes the validator.

### P1.8 Demo AOIs + experiments (T+14 → T+30)
- [ ] Cache with `scripts/cache_aoi.py` (upload `cache/` to the team Drive and put the link in `docs/plan/reports/P1.8.md`):
  - `trishuli_north` (85.28,28.10,85.42,28.29);
  - `trishuli_south` (85.10,27.88,85.30,28.10);
  - one **non-Trishuli** 2026 flood AOI with a same-track pre/post pair. Choose it by T+12 from the Copernicus GFM news list or ReliefWeb, and record why you chose it.
- [ ] **E3c backend consistency** (`docs/results/E3c.md`): the same Trishuli post scene via Sentinel Hub + `lee_sigma` vs SNAP. Report the median and p90 |ΔdB| over stable terrain (HAND > 100 m, slope < 20°, no shadow/layover) [TARGET median ≤ 0.5 dB], plus the agreement of the downstream flood masks (IoU between backends) once P2's model exists.
- [ ] **E5 same-track vs cross-track** (`docs/results/E5.md`): run the pipeline twice on `trishuli_north`:
  1. normal (pre 85A, post 85A 08-28);
  2. `--allow-cross-track`, with pre from 19D (08-24) and post 85A (08-28).

  Report P2's `stable_steep_fpr` and the flood area for both. Hypothesis H3: cross-track > same-track.

### Hand-offs
- **To P2 by T+10:** `cache/trishuli_north` (real s1 + terrain files), for integration and debugging only. Trishuli is the **unseen test scene**: no threshold may be tuned on it. All thresholds are either fixed in advance (`rules`/`gating` in `configs/default.yaml`) or chosen on Kuro Siwo validation events.
- **To P4 by T+10:** a working `stage_s1` + `stage_terrain` in fast mode; by T+24, cached mode for all three AOIs.

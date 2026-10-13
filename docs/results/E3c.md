# E3c — Backend consistency (Sentinel Hub + `lee_sigma` vs SNAP)

**Status: NOT RUN. Blocked on credentials and SNAP** (see `docs/plan/reports/P1.8.md`). No numbers below are
results. The [TARGET] is a target, not a measurement.

## Question
Does the fast backend (D1: Sentinel Hub Process API σ⁰-ellipsoid, orthorectified on COPERNICUS_30, then our
`geo/speckle.lee_sigma`) give the same σ⁰ as the reference SNAP graph (`graphs/s1_cutoff.xml`, Kuro Siwo steps with
Copernicus 30 m DEM and SNAP Lee Sigma)?

## Setup (fixed in advance)
- Scene: the Trishuli post scene `S1D_IW_GRDH_1SDV_20260828T122141_20260828T122206_004326_007FA4_C73B_COG`
  (track 85 ascending), on the trishuli_north grid (85.28,28.10,85.42,28.29; EPSG:32645, 10 m, 1404 × 2125 px).
- Stable terrain mask: HAND > 100 m, slope < 20°, no shadow/layover (from `cache/trishuli_north/{hand,slope}.tif`
  and the post `shadow_layover.tif`), valid in both backends.
- Statistic: median and p90 of |ΔdB| per polarisation (`cutoff.data.snap.backend_consistency`).
  **[TARGET] median ≤ 0.5 dB.**
- Downstream: IoU of the flood masks (hazard classes 1–2) between the two backends, once P2's model exists.

## Procedure
Model: P2's frozen release `model-v1` (`models/cutoff_unet_v1.pt`, git-ignored). Download it once:
`curl -L -o models/cutoff_unet_v1.pt https://github.com/Padmajakachare1911/Cutoff-MAPPING-FLOOD-DAMAGE-FROM-SPACE/releases/download/model-v1/cutoff_unet_v1.pt`
(98 MB; the runner was smoke-tested with it on the mock run on 2026-10-13, see `docs/plan/reports/P1_UPDATES_LOG.md`).

```
python scripts/cache_aoi.py --name e3c_fast --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --out outputs/e3c_fast --stages s1,terrain,model,disturbance,gating --model models/cutoff_unet_v1.pt
python scripts/cache_aoi.py --name e3c_full --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode full --out outputs/e3c_full --stages s1,terrain,model,disturbance,gating --model models/cutoff_unet_v1.pt
```
Then `backend_consistency(read(e3c_fast/s1_post), read(e3c_full/s1_post), hand, slope, shadow)` and the IoU of
`hazard_class ∈ {1, 2}`.

## Results
| Pol | n stable px | median \|ΔdB\| | p90 \|ΔdB\| |
|---|---|---|---|
| VV | — | — (not run) | — |
| VH | — | — (not run) | — |

Flood-mask IoU between backends: — (not run).

## Blockers
- `SH_CLIENT_ID` / `SH_CLIENT_SECRET` (fast backend).
- ESA SNAP `gpt` installed, plus `CDSE_USERNAME` / `CDSE_PASSWORD` (full backend download).
- ~~A P2 checkpoint for the IoU part~~ available since 2026-10-13: release `model-v1` (`models/cutoff_unet_v1.pt`, download command in `E5.md`).

# E3c — Backend consistency (Sentinel Hub + `lee_sigma` vs SNAP)

**Status: RUN on 2026-10-13** (σ⁰ part and downstream IoU; SNAP 14.0.0, Sentinel Hub on CDSE, model `model-v1`).
The [TARGET] is a target, not a measurement; it is **narrowly missed**. Raw numbers in `docs/results/raw/`:
`E3c_sigma0.json`, `E3c_iou.json`, `E3c_full_stage_returns.json` (fast run = `E5_same_stage_returns.json`).

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
Post scene `S1D_..._20260828T122141_..._C73B_COG` on the trishuli_north grid. Fast = Sentinel Hub σ⁰-ellipsoid +
`lee_sigma`; full = `graphs/s1_cutoff.xml` on SNAP 14.0.0 (download 362 s for 1.24 GB, `gpt` 40 s after the AOI subset),
reprojected bilinearly onto the grid. Both valid on 98.83 % of the grid.

| Pol | n stable px | median \|ΔdB\| | p90 \|ΔdB\| | median signed ΔdB (fast − SNAP) |
|---|---|---|---|---|
| VV | 199,867 | **0.588** | 1.752 | −0.199 |
| VH | 199,867 | **0.581** | 1.724 | −0.194 |

[TARGET] median ≤ 0.5 dB: **not met** (0.59 / 0.58 dB). Local incidence angle agrees well: |ΔLIA| median 0.34°,
p90 1.17°.

Diagnostic (not the E3c statistic, no tuning): with both backends averaged over 5 × 5 px blocks (50 m) on the same
stable mask, the median |ΔdB| drops to **0.248 (VV) / 0.241 (VH)** (p90 0.73 / 0.69). Most of the 10 m disagreement is
therefore pixel-scale, not calibration. Likely sources (hypotheses, not separated here):
1. Two Lee-sigma implementations: SNAP estimates the ENL (`estimateENL=true`); ours uses a fixed 4.4 looks.
2. SNAP's output grid is offset by half a pixel from ours (origin x = 327845), so the bilinear reprojection smooths it.
3. Different orthorectification/DEM interpolation chains.

A consistent −0.2 dB offset (fast darker) remains. It is small compared with the 3σ change rule (σ stable 1.31 dB in E5).

### Downstream: hazard maps from the two backends
Fast = `outputs/e5_same` (the E5 same-track run). Full = `outputs/e3c_full`, the whole chain in `--mode full`: all four
scenes through SNAP, SNAP Lee Sigma, no local filter, same model and frozen thresholds. Every stage's outputs passed
`validate_run_dir`, **which is the P1.7 acceptance for full mode**. IoU on pixels observed in both runs:

| Classes | Fast px | Full px | IoU |
|---|---|---|---|
| **flood 1–2 (the E3c statistic)** | 49 | 36 | **0.735** (all 36 full-mode px inside the fast mask; support tiny) |
| hazard 1–4 ("where the flood hit") | 2,432 | 5,960 | 0.313 |
| rule decrease 3 | 1,643 | 3,340 | 0.352 |
| rule increase 4 | 740 | 2,584 | 0.249 |
| permanent water 5 | 97,143 | 86,641 | 0.808 |

Pixel agreement over all classes: 99.19 %.

| Stage return | Fast | Full |
|---|---|---|
| σ stable (disturbance) | 1.312 dB | 0.896 dB |
| stable_steep_fpr | 2.1 × 10⁻⁶ | 0.0 |
| flood high / possible km² | 0.000 / 0.005 | 0.000 / 0.004 |
| rule decrease / increase km² | 0.164 / 0.076 | 0.334 / 0.259 |
| no observation km² | 1.59 | 4.97 |

**Reading:**
- **The model's flood output agrees** (IoU 0.73), but its support is only about 50 px, because the model finds almost
  no flood on Trishuli in either backend.
- **The rule classes are backend-sensitive.** SNAP's output is smoother at 10 m (see the diagnostic above), so its
  scene-wide stable-terrain σ is lower (0.90 vs 1.31 dB). The 3σ threshold drops accordingly and full mode flags about
  2.4× more change pixels. This is the practical cost of the 0.59 dB pixel-scale difference.
- **Thresholds are frozen and nothing was retuned.** The fast backend is the production path (D1); the team should know
  that rule-class areas are not backend-invariant.
- Full mode has more no-observation (4.97 vs 1.59 km²) because the SNAP subset leaves 1.2 % of the grid unfilled at the
  edges (valid 98.83 %).

## Blockers
None. All resolved 2026-10-13: Sentinel Hub OAuth client and CDSE login working, SNAP 14.0.0 installed, model-v1
downloaded.

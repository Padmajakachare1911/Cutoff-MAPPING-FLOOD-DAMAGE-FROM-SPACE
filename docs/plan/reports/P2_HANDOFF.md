# P2 (ML & Hazard): handoff log

**Status (2026-10-14): P2 work is complete, including the C2 real-data check.** `model-v1` stays frozen. The real-data check (`P2.12_real_data.md`) found that the model does not detect the Trishuli or Deir ez-Zor floods on its own (domain shift: gorge, desert); the change-rule layer carries the hazard there. The v1 permanent-water gates, E8 slope evidence, E3 validation result, real-data report and experiment log are included in the submission integration. V1 remains the production default. Experimental v2 stays on its separate branch and is excluded from main. A parked improvement plan is in `P2_model_improvement_plan.md`.

Results: **`docs/results/P2_kuro_results.md`**. Full task list: `docs/plan/02_P2_ml_hazard.md`.

## What to use
| Need | Use |
|---|---|
| Final model | GitHub release `model-v1` → `models/cutoff_unet_v1.pt` (SHA-256 `a2701cfcfbaa1d6facba585cb835aeff95607dadf6d6647ce84cb1d7fe380d46`) |
| Run it in the pipeline | `stage_model(ctx)` with `ctx.model_path="models/cutoff_unet_v1.pt"` (or `cutoff run ... --model models/cutoff_unet_v1.pt` once P4's CLI exists) |
| Before a model exists / as a fallback | `ctx.model_path="b0"` (non-learned baseline) |
| Hazard stages | `cutoff.geo.change.stage_disturbance`, `cutoff.geo.gating.stage_gating`, `cutoff.geo.vectorize.stage_vectorize` |
| Early integration model (superseded) | release `model-early-v0` |

**Frozen means:** no retraining or retuning of the model, τ, T or the `rules`/`gating` thresholds after the EMSR927 check (E4) is run. If E4 shows a problem, report it as a finding.

## Final model (decision record)
- **Model:** `b3_no_slope`, seed 42. U-Net, ResNet-34 encoder, ImageNet init.
- **Data:** Kuro Siwo official split, all 27 train events (9,114 patches; frozen snapshot `index_full.csv`).
- **Slope channel:** held at its training mean (`zero_channels=[6]`).
- **τ / T:** 0.50 / 1.037, chosen on 6 validation events.
- **Why no-slope (D6):** validation was a tie with the slope model (0.638 vs 0.641). The slope channel learned "no floods on steep slopes", which in Himalayan gorges (where GLO-30 inflates valley-floor slope) would silently delete detections; gating downgrades them instead. The test result (slope +0.007) was reported, not used to choose.

| Held-out test (10 events) | IoU | F1 |
|---|---|---|
| b0, classic thresholding | 0.512 | 0.678 |
| B1, published Kuro Siwo SNUNet | 0.676 | 0.807 |
| **Final model, seed 42** | **0.689** | **0.816** |
| Final model, seed 7 (variance check) | 0.688 | 0.815 |

## Machine / environment (Person 2's laptop)
- Windows 11, Python 3.13 (works; the project targets 3.11+), NVIDIA RTX 4050 Laptop 6 GB, CUDA OK (torch 2.6), 15 GB RAM.
- **Repo:** `C:\Users\524ta\OneDrive\Desktop\cuttoff`, inside OneDrive, so never put data here.
- **Data:** `C:\cutoff_data`, set as env var `CUTOFF_DATA_DIR` in the git-ignored `.env`.
  - Kuro Siwo subset: `C:\cutoff_data\kuro` (8.4 GB, `index.csv`, `index_early.csv`, `index_full.csv`, `progress.json`);
  - runs: `C:\cutoff_data\runs\<name>`;
  - B1 weights and their repo: `C:\cutoff_data\b1`.
- **Tests:** `$env:PYTHONPATH="src"; python -m pytest -q -p no:warnings` (the package isn't pip-installed on this machine).
- **PowerShell 5 caveat:** `Set-Content -Encoding utf8` writes a BOM. Use the Edit/Write tools or Python for repo files.
- **Do not switch git branches in this folder while a training run is going** (DataLoader workers re-import `src/`). Use a separate worktree.
- **GPU:** one run at a time. Three runs in parallel were measured 1.5–2× slower overall (GPU 100 %, disk 82 %).

## Status per task
| Task | Status | Where |
|---|---|---|
| P2.1 Kuro Siwo subset | ✅ done: 14,509 patches (train 9,114 / val 1,145 / test 4,250) | `data/kuro_siwo.py`, `scripts/fetch_kuro_subset.py`, `configs/kuro_grd_segments.json` |
| P2.2 SAR input builder | ✅ | `geo/sar.py` (D5 NaN-safe dB, linear pre-mean, D6 slope clip) |
| P2.3 Dataset + stats + QA | ✅ | `data/kuro_siwo.py`, `scripts/kuro_qa.py`, `docs/plan/reports/P2.3_qa.{md,png}` |
| P2.4 Training + calibration | ✅ six models trained | `ml/*`, `configs/train_unet.yaml` |
| P2.5 b0 + stage_model | ✅ | `ml/baselines.py`, `ml/infer.py`, `geo/raster_io.py` |
| P2.6 B1 SNUNet | ✅ | `eval/b1_snunet.py`, `eval/third_party/kurosiwo_snunet.py` (MIT, vendored) |
| P2.7–P2.9 disturbance / gating / vectorise | ✅ | `geo/change.py`, `geo/gating.py`, `geo/vectorize.py` |
| P2.10 τ/T + freeze | ✅ release `model-v1` | `models/cutoff_unet_v1.pt` (git-ignored; download from the release) |
| P2.11 E1/E2/E3/E8 | ✅ | `eval/kuro_eval.py`, `docs/results/P2_kuro_results.md`, `docs/results/raw/` |

## Findings that affect other streams (IMPORTANT)
1. **P1: speckle filtering is mandatory.** On raw speckle the model misses floods (flood probability 0.05 in the mock corridor vs 0.82–0.84 after 7×7 smoothing on a flat floor). Kuro Siwo inputs are Lee-Sigma filtered, so the pipeline's S1 rasters must be too (P1.2 `lee_sigma`), on **both** backends.
2. **The model expects linear σ⁰ with Kuro Siwo's radiometry** (SNAP σ⁰ ellipsoid, no terrain flattening). Do not feed γ⁰ RTC; the SIGMA0_ELLIPSOID choice in D1 matches.
3. **P4: the mock run is unrealistic for model testing** (raw speckle, no flat valley floor). Use it for contract/UI tests only.
4. **`p_flood` is a model score, not a probability:** flood-class calibration error ≈ 0.13 (E8). Dashboard and report must label it so; decisions use τ and the gating tiers.
5. **Kuro Siwo label 3 = unannotated** (ignored).
6. **Steep terrain is unmeasured on Kuro Siwo:** only 8,742 test pixels ≥ 15°. Himalayan performance is only known from E4 (Trishuli vs EMSR927, P4, after the freeze).

## Kuro Siwo download facts (P2.1)
- HF `orion-ai-lab/Kuro-Siwo-GeoTIFFs`, folder `GRD/`: 35 tars × ~20 GB = 699 GB, PAX headers, HTTP Range supported.
- **Sample layout:** `data/<actid>/<aoi>/[<xx>/]<hash>/` containing:
  - `MS1_*` post-event, `SL1_*`/`SL2_*` pre-event (VV, VH);
  - `MK0_MLU` label (0/1/2, plus 3 = unannotated);
  - `MK0_MNA` valid mask;
  - `MK0_DEM` elevation;
  - `info.json`.

  Rasters are 224×224 float32 EPSG:3857, linear σ⁰. AOI dir `00` = unlabelled.
- Event 514 (val) is missing from the tars.
- The HF CDN drops long streams. The fetcher uses 96 MB ranges, resumes at real tar headers, and saves per-segment offsets. Rerunning `python scripts/fetch_kuro_subset.py fetch --jobs 4 --splits val train test --test-per-event 1000` is always safe.

## Open items
1. ~~Real-data check at C2~~ **done 2026-10-14**: `P2.12_real_data.md`. Trishuli `stable_steep_fpr` 2.1 × 10⁻⁶, no observation 1.59 km², Bhote Koshi corridor visible in ΔVV (2× more > 3 dB change than stable terrain), model flood 0.005 km². Deir ez-Zor: the model calls desert "permanent water" (95 km²) and misses the river flood; the rule layer finds 4–6 km² of decrease along the banks.
   - **Integrated P2 branches:** `p2/P2.8-permanent-water-terrain`, `p2/P2.11-evidence-gaps`, `p2/P2.12-real-data-check` and `p2/model-improvement-plan`. No model-v2 branch/checkpoint is included. The project-level freeze and independent E4 remain pending full real-data integration.
   - **For P4's report:** state that the U-Net's real-scene flood signal is near zero in both demo AOIs and that the change rule carries the hazard there.
2. **Optional:** a flood-specific calibration (isotonic on validation) could lower flood ECE, but the improvement would be measured on the same small validation set. Not done; stated as a limitation.
3. **Known domain differences to state in the report:**
   - Kuro Siwo DEM/terrain correction used SRTM; we use GLO-30.
   - Kuro Siwo is lowland-heavy.
   - Training patches are EPSG:3857 resampled; the pipeline runs on UTM at 10 m.

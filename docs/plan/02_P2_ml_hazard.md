# P2 — ML & Hazard stream (Person 2)

> **For agentic workers:** you own the AI component (25 % of the score) and the hazard product. Read `00_MASTER_PLAN.md` and `05_contracts.md` first. Your stage outputs must pass `validate_run_dir`. Never tune anything on Trishuli or EMSR927: thresholds are fixed in `configs/default.yaml` or chosen on Kuro Siwo **validation** events only. TDD, one PR per task.

**You deliver:**
- a U-Net (ResNet-34 encoder, 7 channels) trained on Kuro Siwo's official event split, temperature-calibrated, with τ chosen on validation events;
- the `b0` rule baseline, which the pipeline uses until your model exists;
- the stages `model`, `disturbance`, `gating` and `vectorize`;
- experiments E1, E2, E3 and E8, with result tables in `docs/results/`.

**Files you own:** `src/cutoff/geo/{sar,change,gating,vectorize}.py`, `src/cutoff/ml/{model,losses,metrics,train,calibrate,infer,baselines}.py`, `src/cutoff/data/kuro_siwo.py`, `eval/{kuro_eval,baselines}.py`, `notebooks/colab_train.ipynb`, `scripts/fetch_kuro_subset.py`, `configs/train_unet.yaml`, `tests/test_p2_*.py`, `docs/results/E{1,2,3,8}.md`.

**Verified facts (2026-10-12):**
- Kuro Siwo on Hugging Face:
  - `orion-ai-lab/Kuro-Siwo-GeoTIFFs` (1.02 TB, CC BY 4.0), with folders `GRD/` and `SLC/` of numbered tar archives (`GRD/00034.tar`);
  - `orion-ai-lab/Kuro-Siwo-Webdataset` (1.96 TB), with `train_GRD/`, `test_GRD/`, ... of `shard-NNNNN.tar`.
- A GRD sample has `flood_vv/vh.npy` (post), `sec1_vv/vh.npy`, `sec2_vv/vh.npy` (2 pre), `dem.npy`, `mask.npy` (0 no water, 1 permanent, 2 flood), `valid_mask.npy`, `info.json`. All arrays are float32.
- The official split comes from `configs/train/data_config.json` and is copied into `configs/kuro_siwo_splits.yaml`: 27 train, 7 val, 10 test activations.
- Kuro Siwo σ⁰ is **linear**: SNAP Calibration with `outputImageScaleInDb=false`; reference mean VV 0.0953, VH 0.0264; `clamp_input` 0.15.
- Released weights (Dropbox, linked from the repo README): FloodViT and SNUNet.
- The repo's trainer uses `--dem/--slope` flags, and its default config has both effectively `false`.

---

### P2.0 Setup (T+0 → T+1)
- [ ] Get a GPU: Colab (Pro if possible) or Kaggle (T4/P100). Create an HF token. Set up a Google Drive folder `cutoff/kuro/` shared with the team. Run `make test` (green).

### P2.1 Kuro Siwo subset — START FIRST, runs in the background (T+1 → T+6)
**Files:** `scripts/fetch_kuro_subset.py`, `src/cutoff/data/kuro_siwo.py` (index part), `tests/test_p2_kuro_index.py`
- [ ] **Discovery (time box 45 min):**
  1. `HfApi().list_repo_tree("orion-ai-lab/Kuro-Siwo-GeoTIFFs", path_in_repo="GRD", repo_type="dataset")` gives the tar names and sizes.
  2. Stream the first tar with `requests` + `tarfile.open(fileobj=..., mode="r|")` and print the first 30 member names plus one `info.json`.
  3. Record the folder pattern, the info.json keys (event/activation id, coordinates, dates) and the total GRD size in `docs/plan/reports/P2.1.md`.
- [ ] **Streaming filter (no full download):** iterate over the GRD tars in streaming mode. Group members by sample folder. Keep a sample only if:
  - its event is in the official split;
  - its event is not within 100 km of (28.1 N, 85.3 E) (use the info.json coordinates or the repo `catalogue/`);
  - its split quota isn't full.
- [ ] Quotas:
  - **val and test: keep every sample** (they define E1);
  - train: ≤ 600 samples per event, with ≥ 50 % containing flood pixels;
  - stop at ~12 k train samples.
- [ ] Write each kept sample as `data/kuro/<split>/<event>/<sample>.npz`: float16 `vv_pre1, vh_pre1, vv_pre2, vh_pre2, vv_post, vh_post, dem`, plus uint8 `mask` and `valid`. Also append a row to `data/kuro_index.csv` (`path, split, event, flood_frac, perm_frac, valid_frac, slope_p50, slope_p90`).
- [ ] Make it resumable: skip tars already listed in `data/kuro_done.txt`. Run it on the Colab VM writing to Drive. Budget: ≤ 60 GB on disk [TARGET].
- [ ] If the HF GeoTIFFs tars can't be streamed, use the webdataset shards (`train_GRD/`, `test_GRD/`) the same way. If neither is usable by T+6, use the repo's `download_kuro_siwo.sh` for a few events, and say so.
- [ ] Test (offline): with two fake sample folders tarred in memory, the filter keeps only wanted events, respects quotas, and the npz round-trips.

### P2.2 SAR input builder with the D5/D6 fixes (T+1 → T+2)
**File:** `src/cutoff/geo/sar.py`, `tests/test_p2_sar.py`
```python
from cutoff.contracts import CHANNELS, DB_CEIL, DB_FLOOR, SLOPE_CLIP_DEG

def to_db(linear):
    """Linear sigma0 -> dB. Non-finite or <= 0 stays NaN (D5: never invent data). Finite values clipped."""
    lin = np.asarray(linear, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        db = 10.0 * np.log10(np.where(lin > 0, lin, np.nan))
    return np.clip(db, DB_FLOOR, DB_CEIL).astype(np.float32)   # np.clip keeps NaN

def pre_mean_linear(pre_stack):           # (T, 2, H, W) linear -> (2, H, W) linear, NaN-aware mean
def build_input_stack(pre_mean_lin, post_lin, slope_deg):
    """(2,H,W) linear, (2,H,W) linear, (H,W) deg -> (7,H,W) float32 in CHANNELS order; slope clipped to SLOPE_CLIP_DEG."""
```
- [ ] Tests:
  - `to_db(0.1) == -10`;
  - `to_db(0)`, `to_db(nan)` and `to_db(-1)` are NaN (**this is the D5 bug fix — the blueprint returned −30**);
  - the stack has shape (7, H, W) and `x[4] == x[2] - x[0]`;
  - slope 40° becomes 15°;
  - a NaN in post makes channels 2–5 NaN at that pixel.

  Note: the pipeline passes the pre-**mean** (P1 writes `s1_pre_mean.tif`), while training averages Kuro Siwo's 2 pre scenes in linear units first. That is the same operation.

### P2.3 Dataset, normalisation stats and QA (T+2 → T+5)
**File:** `src/cutoff/data/kuro_siwo.py`, `tests/test_p2_dataset.py`
- [ ] `KuroSiwoDataset(index_csv, split, mean, std, augment, seed)` reads the npz and returns `x` float32 (7, 224, 224), normalised, NaN → 0 **after** normalisation, plus `y` int64 with 255 where `valid == 0` or the input is non-finite.
- [ ] Slope comes from `dem` via `slope_degrees(dem, 10.0)` (import from P1's `cutoff.geo.terrain`; until P1 merges, use a local `np.gradient` helper with the same formula).
- [ ] Augmentation (train only):
  - a radiometric gain of ±1 dB on channels 0–3 (the same gain on pre and post keeps Δ unchanged: apply it to channels 0–3 and leave 4–5);
  - Gaussian noise σ = 0.05 in normalised units on channels 0–5;
  - **no flips by default** (they are an E3 ablation).
- [ ] `compute_channel_stats(train events only)` over valid pixels (≤ 2000 samples), saved to `models/stats.json`.
- [ ] QA: plot 20 random samples per split (VV dB pre/post, Δ, slope, mask) to `docs/plan/reports/P2.3_qa.png`. Report the per-split class histogram and the slope distribution (expect the steep fraction to be tiny; that's why D6 exists).
- [ ] Tests on a fake sample: shapes, dtypes, the ignore index, and no NaN in `x`.

### P2.4 Model, loss, training loop, calibration (T+3 → T+8 code; T+8 → T+20 GPU)
**Files:** `src/cutoff/ml/{model,losses,metrics,train,calibrate}.py`, `configs/train_unet.yaml`, `notebooks/colab_train.ipynb`, `tests/test_p2_model.py`
- [ ] Port from blueprint v1.0 §18.4–18.7 (`docs/research/01_blueprint_v1.0.md`), with these changes:
  - `build_model`: `smp.Unet("resnet34", encoder_weights="imagenet", in_channels=7, classes=3)` (smp adapts the first conv);
  - `save_checkpoint` meta must contain the keys in `05_contracts.md` §5;
  - `load_checkpoint` raises if `meta["channels"] != list(CHANNELS)`;
  - the loss is CE (class weights 1, 1, 3, ignore 255) + soft Dice on the flood class;
  - training uses AdamW 3e-4, cosine schedule, AMP on CUDA, batch 16, ≤ 30 epochs, early stop on **validation-event flood IoU** (patience 6), and saves `last.pt` every epoch so Colab disconnects resume;
  - `fit_temperature` (LBFGS on log T) runs on validation logits subsampled 1/64.
- [ ] Tests (CPU, tiny):
  - forward shape (1, 3, 224, 224);
  - the loss is finite with ignore pixels;
  - **overfit test**: 8 synthetic patches, 60 steps, loss falls by > 80 %;
  - the checkpoint round-trips, and a bad checkpoint raises;
  - `T > 0` and calibration leaves the argmax unchanged.
- [ ] Training runs (record each in `docs/experiment_log.md`: git commit, config hash, seed, GPU, minutes):
  1. **P-7ch** (main), seed 42;
  2. **B2 post-only** (channels 2–3);
  3. **B3-6ch** (no slope);
  4. if time allows: flips on, and seeds 7 and 1234 for P-7ch.
- [ ] Publish `models/cutoff_unet_v1.pt` (best by validation flood IoU) to the team Drive **and** as a GitHub release asset `model-v1`. Write the download URL into `docs/plan/reports/P2.4.md`.

### P2.5 `b0` baseline + `stage_model` with tiled inference (T+5 → T+10) — **needed for C1**
**Files:** `src/cutoff/ml/baselines.py`, `src/cutoff/ml/infer.py`, `tests/test_p2_infer.py`
- [ ] **B0** (classic, non-learned; computed per scene over valid pixels):
  - `t = otsu(VV_post_db)`;
  - `p_flood = σ((t − VV_post_db)/1.0) · σ((−ΔVV_db − 3)/1.0)`;
  - `p_perm = σ((t − VV_pre_db)/1.0) · σ((t − VV_post_db)/1.0)`;
  - `p_no = 1 − p_flood − p_perm`, clipped at 0 and renormalised.

  Write the formula in the docstring. τ = 0.5, T = 1, `model_version = "b0"`.
- [ ] `predict_proba(model, x_norm, tile=224, overlap=64, temperature, batch, device)`: Hann-weighted blending; pixels with any non-finite input channel get NaN probabilities (works with D5). Port it from blueprint §18.8.
- [ ] `stage_model(ctx)`:
  1. Read `s1_pre_mean`, `s1_post` and `slope`.
  2. Build the stack.
  3. If `ctx.model_path == "b0"`, run B0; otherwise load the checkpoint, normalise with meta mean/std and predict on CUDA if available.
  4. Write `p_model.tif`.
  5. Return `model_version`, `flood_threshold` (τ from meta) and `temperature`.
- [ ] Tests:
  - on the mock run, `stage_model` with b0 writes a valid `p_model.tif` (validator), and flood probability is higher inside the mock flood corridor than outside;
  - tiled inference on a 300 × 260 input matches the shape, sums to 1, and NaN stays NaN;
  - a random-weights checkpoint runs end-to-end.

### P2.6 B1: released SNUNet weights (optional, time box 2 h, T+12 → T+20)
- [ ] Download the SNUNet weights from the KuroSiwo README links and read `models/` + `dataset/Dataset.py` in their repo for the input format (linear, clamped at 0.15, normalised with their mean/std, pre/post order).
- [ ] Wrap them as `cutoff.ml.baselines.snunet_proba(...)` for E1 only. If the format can't be resolved in 2 h, drop B1 and say so in E1.

### P2.7 Disturbance stage, D9 (T+6 → T+10) — **needed for C1**
**File:** `src/cutoff/geo/change.py`, `tests/test_p2_change.py`
- [ ] `disturbance(d_db, pre_vv_db, hand, valid, k=3, hand_corridor_m=60, hand_stable_m=100, strata=3, min_px=20)`:
  1. `stable = valid & (hand > 100)`.
  2. Split stable pixels into `strata` bins by **pre-event VV dB terciles**, and estimate a robust σ (1.4826·MAD) and median per bin.
  3. Assign every pixel the σ/median of its own pre-VV bin, so dark valley-floor fields aren't judged by forest statistics.
  4. `z = (d − med_bin)/σ_bin`; inside the corridor (`hand ≤ 60`), `z < −k` → 1 and `z > k` → 2.
  5. Remove connected components smaller than `min_px` (`scipy.ndimage.label`, 8-connectivity).
  6. Set −1 where invalid.
  7. Raise a clear error if fewer than 100 stable pixels exist.
- [ ] `stage_disturbance(ctx)` uses ΔVV (dB); invalid = shadow/layover | NaN. It returns `sigma_stable_db` (the pixel-weighted mean of the bin σ), `k_sigma` and `n_stable_px`.
- [ ] Tests:
  - the synthetic case from blueprint §18.16 passes;
  - a 10-pixel speck is removed;
  - a stratum with a different noise level gets its own σ;
  - pixels outside the corridor are never flagged.

### P2.8 Gating stage (T+8 → T+11) — **needed for C1**
**File:** `src/cutoff/geo/gating.py`, `tests/test_p2_gating.py`
- [ ] Implement the truth table in `05_contracts.md` §2 exactly. Use the flag bits from `contracts.Flag`, casting with `np.uint8(int(flag))` because numpy won't OR an int64 into uint8.
  - τ comes from `ctx.summaries["model"]["flood_threshold"]`.
  - S2 layers are used only where `s2_clear != 255`.
- [ ] `stable_steep_fpr = mean(class ∈ {1,2} over pixels with slope > 20° & HAND > 100 m & observable)`, or `None` if no such pixels exist.
- [ ] Tests, one per row of the truth table:
  - steep model flood → 2;
  - an S2-agreeing possible → 1;
  - an S2-clear-no-water high → 2 unless disturbance decreased;
  - shadow → 254;
  - permanent → 5;
  - the flags carry every reason.

### P2.9 Vectorise stage (T+9 → T+11)
**File:** `src/cutoff/geo/vectorize.py`, `tests/test_p2_vectorize.py`
- [ ] `rasterio.features.shapes` on classes 1–4. Drop polygons smaller than 5 px, simplify by 5 m (`preserve_topology=True`), add `area_m2`, write layer `hazard`.
- [ ] Class areas come from pixel counts × |a·e| (refuse a non-UTM CRS). `no_observation_km2` = count(254) × pixel area.
- [ ] Tests: areas on a 100 × 100 block = 1 km²; EPSG:3857 raises.

### P2.10 Choose τ and T; freeze the model (T+20 → T+28)
- [ ] On **validation events only**: compute the flood-F1-vs-τ curve for P-7ch, pick the τ that maximises F1, fit T, and write both into the checkpoint meta → `cutoff_unet_v1.pt`.
- [ ] Hand `models/cutoff_unet_v1.pt` to P4 before T+28. After FREEZE (T+32) it must not change.

### P2.11 Experiments E1, E2, E3, E8 (T+20 → T+32)
**Files:** `eval/kuro_eval.py`, `docs/results/E1.md`, `E2.md`, `E3.md`, `E8.md`
- [ ] **E1** held-out quality: on the 10 official test events, compare B0, B1 (if done), B2, B3-6ch and P-7ch. Report a per-event table (precision, recall, F1, IoU, support px) plus the pooled mean ± sd over seeds when available. Metrics come from `ConfusionMeter` (blueprint §18.7), flood class, ignoring 255.
- [ ] **E2** slope strata: report the same models' metrics per slope bin (0–5°, 5–15°, > 15°), and **report support px** (it will be small above 15°; say so). Compute the stable-steep FPR on the Trishuli runs (unlabelled, allowed) from the gating stage.
- [ ] **E3** ablations: post-only vs +pre vs +diff vs +slope (6ch vs 7ch), and flips on/off if trained. Report validation **and** test numbers.
- [ ] **E8** calibration: ECE (10 bins) before and after temperature scaling, overall and per slope bin, on validation events.
- [ ] Every table names the checkpoint, config hash, split and seed. No number goes into the report without its table.

### Hand-offs
- **To P4 at C1 (T+10):** stages model (b0), disturbance, gating and vectorize merged and validated on the mock run and on P1's Trishuli cache.
- **To P4 at C2 (T+24):** a checkpoint URL; the pipeline runs with `--model models/cutoff_unet_v1.pt`.
- **To P4 by T+30:** E1, E2 and E8 markdown tables for the report.

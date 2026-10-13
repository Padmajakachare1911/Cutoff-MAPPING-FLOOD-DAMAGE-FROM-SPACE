# Experiment log (P2.4 training runs)

Every training run of the Kuro Siwo U-Net. Values come from each checkpoint's `meta` (`git_commit`, `config_hash`, `config`, `best_val_flood_iou`, `temperature`, `flood_threshold`, `created_utc`) and its `history.json` (epochs, per-epoch seconds). Raw histories: `docs/results/raw/history_<run>.json`.

**Common to all runs:** U-Net, ResNet-34 encoder, ImageNet init; AdamW lr 3e-4, weight decay 1e-4; cosine schedule with `T_max` = 30 epochs; batch 16; AMP; CE (class weights 1, 1, 3) + flood soft-Dice; early stop on validation-event flood IoU, patience 6; no flips. **GPU:** NVIDIA RTX 4050 Laptop, 6 GB (Person 2's laptop), one run at a time. **Validation events:** 279, 437, 520, 559, 1111003, 1111008.

| Run | Purpose | Data snapshot | Channels | Seed | Git commit | Config hash (first 12) | Epochs run (best) | GPU min | Best val flood IoU | τ / T | Created (UTC) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p7_early | early integration model | `index_early.csv` (20 train events) | 7 | 42 | `b588310` | `67b0204b5fb5` | 23 (16) | 22.7 | 0.651 | 0.40 / 1.228 | 2026-10-12 17:08 |
| b3_no_slope_early | early D6 evidence | `index_early.csv` | 6 (slope at mean) | 42 | `26b38bc` | `e41190379d13` | 18 (11) | 22.9 | 0.646 | 0.60 / 1.166 | 2026-10-12 17:36 |
| **b3_no_slope** | **final model → `model-v1`** | `index_full.csv` (27 train events, 9,114 patches) | 6 (slope at mean) | 42 | `1e1635c` | `ac3672815bef` | 18 (11) | 39.7 | 0.638 | 0.50 / 1.037 | 2026-10-12 18:24 |
| p7 | D6 ablation (with slope) | `index_full.csv` | 7 | 42 | `1e1635c` | `317b30007569` | 15 (8) | 34.8 | 0.641 | 0.55 / 1.013 | 2026-10-12 19:00 |
| b2_post_only | H1 ablation | `index_full.csv` | post VV/VH only | 42 | `1e1635c` | `85a8f9fbdfc0` | 19 (12) | 43.0 | 0.533 | 0.55 / 1.126 | 2026-10-12 19:44 |
| b3_no_slope_seed7 | seed variance of the final model | `index_full.csv` | 6 (slope at mean) | 7 | `1e1635c` | `e97a7f37892e` | 17 (10) | 33.1 | 0.650 | 0.55 / 1.072 | 2026-10-12 20:18 |

"Epochs run" is a count; "(best)" is the 0-based index of the chosen epoch. "GPU min" is the sum of the per-epoch wall times in `history.json`. The first epoch includes data-cache warm-up, and runs overlapping other GPU jobs ran slower.

## Notes
- **Early stopping ended every run before the 30-epoch cosine schedule finished.** The four full-data runs had their last epoch at index 14–18, with the learning rate still at 35–55 % of its peak; their chosen epochs (8–12) ran at 65–83 % of the peak (multiplier 0.5·(1 + cos(π·epoch/30))). Validation IoU fluctuates ±0.03–0.07 between epochs. See `docs/plan/reports/P2_model_improvement_plan.md` (finding 1). This does not change any reported result; it is a known limitation of the frozen model.
- **The early models score higher on validation than the full-data models** (0.651 / 0.646 vs 0.641 / 0.638), yet they are 0.04 lower on test (`docs/results/P2_kuro_results.md`, E1/E3). The 6-event validation set is noisy; this is why the D6 choice used a rule fixed in advance instead of the validation ranking.
- Test numbers per run: `docs/results/P2_kuro_results.md` (E1). Calibration: E8 there and `docs/results/raw/val_e8*.json`.

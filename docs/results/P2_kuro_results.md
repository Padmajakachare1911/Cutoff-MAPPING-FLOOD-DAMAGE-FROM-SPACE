# P2 results: flood segmentation on Kuro Siwo (E1, E2, E3, E8)

All numbers are measured, from `eval/kuro_eval.py`. Flood-class metrics are pixel-level over valid pixels; Kuro Siwo label 3 (unannotated) is ignored.

- **Data:** the official Kuro Siwo event split, a subset fetched by `scripts/fetch_kuro_subset.py`.
  - **train:** 27 events, 9,114 patches (≥ 50 % with flood pixels by design);
  - **validation:** 6 events, 1,145 patches (event 514 is not in the published GeoTIFF tars);
  - **test:** 10 events, 4,250 patches (3 events capped at 1,000).
- **Test events** were never used for training, threshold or temperature selection, or model choice.
- **Model selection** used validation events only. Test numbers are reported, not used to choose.

## E1: held-out test events (10 events, 4,250 patches)

| Model | Input | Train data | τ | Precision | Recall | F1 | IoU |
|---|---|---|---|---|---|---|---|
| b0: Otsu change rule (non-learned) | pre/post VV | — | 0.50 | 0.720 | 0.640 | 0.678 | 0.512 |
| B1: released Kuro Siwo SNUNet (Bountos et al. 2024), zero-shot | pre1 + post (VV, VH, DEM) | Kuro Siwo (authors) | 0.50 | **0.849** | 0.768 | 0.807 | 0.676 |
| b2_post_only (H1 ablation) | post VV/VH only | 100 % | 0.55 | 0.650 | 0.800 | 0.717 | 0.559 |
| p7_early | 7 ch incl. slope | 60 % | 0.40 | 0.821 | 0.759 | 0.789 | 0.652 |
| b3_no_slope_early | 6 ch (slope at mean) | 60 % | 0.60 | 0.804 | 0.766 | 0.785 | 0.646 |
| p7 (D6 ablation: with slope) | 7 ch incl. slope | 100 % | 0.55 | 0.846 | 0.797 | **0.821** | **0.696** |
| **b3_no_slope (FINAL, `cutoff_unet_v1.pt`, seed 42)** | **6 ch (slope at mean)** | **100 %** | **0.50** | 0.813 | **0.819** | 0.816 | 0.689 |
| b3_no_slope, seed 7 (variance check) | 6 ch | 100 % | 0.55 | 0.839 | 0.793 | 0.815 | 0.688 |

### Per event (flood IoU)
| Event | b0 | B1 SNUNet | p7 | **b3_no_slope (final)** |
|---|---|---|---|---|
| 205 | 0.462 | 0.575 | 0.573 | 0.571 |
| 277 | 0.523 | 0.781 | 0.776 | 0.762 |
| 321 | 0.459 | 0.611 | 0.598 | 0.606 |
| 411 | 0.559 | 0.754 | 0.755 | 0.744 |
| 445 | 0.697 | 0.777 | 0.746 | 0.725 |
| 561 | 0.727 | 0.780 | 0.769 | 0.776 |
| 562 | 0.309 | 0.606 | 0.794 | **0.872** |
| 1111002 | 0.263 | 0.599 | 0.638 | 0.609 |
| 1111007 | 0.516 | 0.655 | 0.671 | 0.658 |
| 1111013 | 0.543 | 0.597 | 0.615 | 0.590 |
| mean of events | 0.506 | 0.674 | 0.694 | 0.691 |

**Reading:**
- The final model beats classic thresholding by **+0.18 IoU**.
- It is **on par with the published SNUNet**: +0.013 pooled IoU and +0.017 mean-of-events. Much of that gain comes from one event (562: 0.872 vs 0.606), and SNUNet is slightly ahead on most other events (typically by 0.01–0.05).
- Recall (0.819 vs 0.768) is the clearest advantage: fewer missed flood pixels.
- **Seed check:** retraining the final model with seed 7 gives test IoU 0.688 vs 0.689 (mean of events 0.686 vs 0.691) and reproduces the event-562 result (0.869). The lead over SNUNet (+0.012 to 0.013) holds for both seeds. The spread between two seeds is ~0.001, which is small but only two runs.

## E2: by slope stratum (test, all events pooled; IoU, support px)

| Slope | b0 | B1 SNUNet | p7_early | b3_no_slope_early | b3_no_slope (final) |
|---|---|---|---|---|---|
| 0–5° | 0.516 (10,887,913) | 0.678 | 0.653 | 0.648 | **0.692** |
| 5–15° | 0.355 (164,760) | 0.566 | 0.568 | 0.560 | 0.556 |
| ≥ 15° | 0.249 (8,742) | 0.383 | 0.326 | 0.273 | 0.351 |

Every model degrades on slopes. The ≥ 15° stratum has only 8,742 test pixels, too few to rank models. **Kuro Siwo cannot measure Himalayan-gorge performance.** That is evaluated on Trishuli vs EMSR927 (E4, check-only, after the freeze), and is why gating downgrades steep detections to "possible" instead of trusting them.

## E3: ablations (test IoU)

| Question | Comparison | Result | Conclusion |
|---|---|---|---|
| H1: does same-track before/after help? | post-only 0.559 vs pre+post+change 0.689 | **+0.130** (threshold +0.02) | **Confirmed.** Without the pre-event image, precision drops 0.81 → 0.65: always-dark surfaces get confused with new water. |
| D6: does the slope channel help? | with slope 0.696 vs without 0.689 (validation 0.641 vs 0.638) | +0.007 test, +0.003 validation | **No measurable benefit.** Rejected: see the decision record. |
| Data size | 60 % → 100 % (no-slope) | 0.646 → 0.689 | More events help (+0.04). |

## E8: calibration (validation events)

| Model | T (fitted) | All-class ECE | Flood ECE, T = 1 | Flood ECE, fitted T |
|---|---|---|---|---|
| b3_no_slope (final) | 1.037 | 0.002 | 0.139 | **0.130** |
| p7 | 1.013 | 0.002 | 0.105 | 0.103 |

All-class ECE is near zero because most pixels are easy "no water". **Flood-class ECE ≈ 0.13**: a flood score of 0.8 is not a calibrated 80 % probability. Temperature scaling barely changes it (T ≈ 1). Consequence: `p_flood` is shown as a "model score", and decisions use τ (chosen on validation) and gating tiers. This is a stated limitation.

## Decision record: final model = `b3_no_slope` (seed 42)
1. **Rule fixed in advance:** choose on validation, and prefer no-slope unless it is clearly worse.
2. **Validation:** p7 0.641 vs b3_no_slope 0.638, a tie within the ±0.05 epoch-to-epoch noise of this 6-event validation set.
3. **Physical argument** (mock-valley diagnostic, `docs/plan/reports/P2_HANDOFF.md`): the slope channel teaches "no floods on steep slopes". In Himalayan gorges, GLO-30 smooths valley walls into the floor, so real flooded floors can look 15–25° steep. A slope model would **silently delete** those detections; gating instead marks them "possible".
4. The test result (+0.007 for p7) is reported but **not** used for the choice; doing so would turn the test set into a tuning set.

## Baselines and fairness notes
- **B1** reproduces the authors' input format (clamp 0.15, their mean/std, DEM channel). The input order was chosen on validation: pre→post IoU 0.624 vs post→pre 0.000. B1 is used zero-shot; it may have been trained with data overlapping our splits differently (not verifiable), so it is a reference, not a controlled comparison.
- **b0** uses a per-patch Otsu threshold here (per scene in the pipeline).
- The Kuro Siwo paper reports flood F1 > 0.80 for its best models on its own test setup; our final model reaches F1 0.816 on our test subset. These figures are comparable in level, but the subsets differ.

## Reproduce
```
python scripts/fetch_kuro_subset.py fetch --jobs 4 --splits val train test --test-per-event 1000
python -m cutoff.ml.train --name b3_no_slope        # also: p7, b2_post_only, b3_no_slope_seed7
python eval/kuro_eval.py --split test --models b0 "b1:<snunet.pt>:pre_post" <ckpts...>
python eval/kuro_eval.py --split val --calibration --models <ckpts...>
```
Raw outputs: `docs/results/raw/`.

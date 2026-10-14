# P2: model improvement plan (parked, not started)

**Status (2026-10-13): parked.** `model-v1` stays the frozen model. This page records the options checked after the freeze, so the team can decide later whether to try any of them **before** P4 tags `frozen-v1` and runs E4. After that tag, nothing here may be done (see `P2_HANDOFF.md`, "Frozen means").

## Where we stand
Held-out test, 10 Kuro Siwo events (`docs/results/P2_kuro_results.md`):

| Model | Test IoU | F1 |
|---|---|---|
| b0, classic thresholding | 0.512 | 0.678 |
| B1, published Kuro Siwo SNUNet (zero-shot) | 0.676 | 0.807 |
| `model-v1` (b3_no_slope, seed 42) | 0.689 | 0.816 |

## Can we claim "better than every published model"? No.
- **Different test sets.** The Kuro Siwo paper reports flood F1 > 0.80 for its best models on its own test setup ([arXiv 2311.12056](https://arxiv.org/html/2311.12056)). Our 0.816 is on our subset (3 test events capped at 1,000 patches). The two numbers are at the same level, but they don't rank against each other. Foundation-model benchmarks (PANGAEA, TerraMind, Prithvi) use other protocols and metrics.
- **The lead over SNUNet is narrow and comes mostly from one event.** Event 562 gives 0.872 vs 0.606; SNUNet is ahead by 0.01–0.05 on most other events.
- **Validation noise is larger than the gains we would chase.** Validation flood IoU moves ±0.03–0.07 from epoch to epoch (`docs/results/raw/history_*.json`).
- **The benchmark is lowland.** A +0.01 gain on Kuro Siwo says nothing about Himalayan gorges. E4 (Trishuli vs EMSR927) does, and on real same-track Trishuli the model alone flags only 0.005 km² (`docs/results/E5.md`).

## Findings from the post-freeze check
1. **The learning-rate schedule never annealed.** `CosineAnnealingLR(T_max=epochs=30)` (`src/cutoff/ml/train.py`), but early stopping (patience 6) ended every run at epochs 15–18. The chosen checkpoints come from epochs 8–12, when LR was still 65–83 % of its peak (multiplier 0.5·(1 + cos(π·epoch/30))), which are the noisiest epochs. See `docs/experiment_log.md`.
2. **The two-seed ensemble, measured on validation only** (`eval/val_ensemble.py`, raw output `docs/results/raw/val_ensemble.json`; the test split was not read):

   | Validation (6 events), τ = 0.50 | Flood IoU |
   |---|---|
   | `model-v1` (seed 42) | 0.637 |
   | b3_no_slope seed 7 | 0.649 |
   | mean-probability ensemble | **0.653** |

   That is +0.015 over `model-v1` but only +0.003 over seed 7 alone, inside the validation noise. The best τ is 0.50–0.55 for all three. Inference cost doubles.
3. **Validation event 1111003 scores IoU ≈ 0.07 for every model** (0.088 / 0.064 / 0.072). Either it has unusual labels or it is a real failure case. It is a large part of the validation noise. Worth a look before any selection based on validation.

## Options, ranked by evidence
| # | Option | Evidence | Cost | Expected effect |
|---|---|---|---|---|
| A | **More training data**: raise the per-event train cap (600) and fetch more patches | 60 % → 100 % of train events gave **+0.04** test IoU (E3) | hours of download (flaky HF CDN, resumable fetcher) + ~1 h training | largest measured lever |
| B | **Fix the schedule**: set `T_max` to the real budget (or train all 30 epochs without early stopping) and average the weights of the last epochs (SWA/EMA) | finding 1 | ~1 h per run on the RTX 4050 | unknown until measured; at least more stable selection |
| C | **Seed ensemble** (seed 42 + seed 7, already trained) | finding 2 | no training; 2× inference | small (+0.003 to +0.015 val), possibly noise |
| D | Flips augmentation (`p7_flips`, planned E3 ablation) | none yet | ~1 h | unknown |

Not recommended in the time left: bigger encoders, foundation models, or new architectures. They need several runs each, and validation is too noisy to pick between them.

## Rules if any option is tried
1. Choose **only on validation events.** Then evaluate the **single** final candidate on test **once**. Running several candidates on test and keeping the best turns the test set into a tuning set.
2. Never use Trishuli or EMSR927 to choose anything.
3. A changed model is a new release `model-v2`. Rerun E1, E2 and E8, update `P2_kuro_results.md` and `P2_HANDOFF.md`, and tell P4 (pipeline `--model` path, E4 inputs).
4. Everything must happen before `git tag frozen-v1`.

## Recommendation
Keep `model-v1`. The score that matters is the Himalayan check (E4) and the real-data behaviour, not +0.01 on a lowland benchmark. If time is left after the remaining P2 items, try **A then B**, selecting on validation only.

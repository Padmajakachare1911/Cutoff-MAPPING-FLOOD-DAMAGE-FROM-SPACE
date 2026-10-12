# P2 (ML & Hazard) — handoff log

This file is kept current after every P2 task, so another agent can continue at any point. Read `docs/plan/02_P2_ml_hazard.md` for the full task list.

## Machine / environment (Person 2's laptop)
- Windows 11, Python 3.13 (works; the project targets 3.11+). NVIDIA RTX 4050 Laptop **6 GB**, CUDA OK in torch 2.6. 15 GB RAM.
- Repo: `C:\Users\524ta\OneDrive\Desktop\cuttoff` (inside OneDrive — **never put data here**).
- Data: `C:\cutoff_data` (env var `CUTOFF_DATA_DIR`, set in the git-ignored `.env`). Kuro Siwo goes to `C:\cutoff_data\kuro`.
- Run tests with `$env:PYTHONPATH="src"; python -m pytest -q -p no:warnings` (the package isn't pip-installed on this machine).
- PowerShell 5 caveat: `Set-Content -Encoding utf8` writes a BOM. Use the Edit/Write tools or Python for repo files.

## Status per task

| Task | Status | Where | Notes |
|---|---|---|---|
| P2.1 Kuro Siwo subset | **code done; index running; fetch not started** | `src/cutoff/data/kuro_siwo.py`, `scripts/fetch_kuro_subset.py`, `tests/test_p2_kuro_index.py` | see "Kuro Siwo facts" below |
| P2.2 SAR input builder | done | `src/cutoff/geo/sar.py`, `tests/test_p2_sar.py` | D5 NaN-safe dB, linear pre-mean, D6 slope clip |
| P2.3 Dataset + stats | **code done** (merged PR #2); QA plot todo once data exists | `data/kuro_siwo.py` (`sample_to_input`, `KuroSiwoDataset`, `compute_channel_stats`) | slope uses ground spacing 10·cos(lat) m (EPSG:3857 patches) |
| P2.4 Model/loss/train/calibrate | **code done** (merged PR #2); **training not run yet** | `ml/{model,losses,metrics,calibrate,train}.py`, `configs/train_unet.yaml` | run: `python -m cutoff.ml.train --name p7` (then `b3_no_slope`, `b2_post_only`); outputs in `C:\cutoff_data\runs\<name>\<name>.pt`; `--resume` after an interruption |
| P2.5 b0 + stage_model | done | `ml/baselines.py`, `ml/infer.py`, `geo/raster_io.py`, `tests/test_p2_infer.py` | Otsu tie-break = middle of the plateau |
| P2.6 B1 SNUNet | todo (optional, time box 2 h) | | |
| P2.7 disturbance | done | `geo/change.py` | D9 final: strata=1, fallback chain for lowland AOIs |
| P2.8 gating | done | `geo/gating.py` | exact truth table in `05_contracts.md` §2 |
| P2.9 vectorise | done | `geo/vectorize.py` | empty hazard writes an empty Polygon layer |
| P2.10 τ/T + freeze checkpoint | todo | | validation events only |
| P2.11 E1/E2/E3/E8 | **harness done** (PR #3); not run yet | `eval/kuro_eval.py` | `python eval/kuro_eval.py --split test --models b0 <ckpts...>` → `docs/results/kuro_test.{md,json}`; `--split val --calibration` for E8 |

## Kuro Siwo facts discovered (verified 2026-10-12, P2.1)
- HF `orion-ai-lab/Kuro-Siwo-GeoTIFFs`, folder `GRD/`: **35 tars × ~20 GB = 699 GB**, PAX headers, HTTP Range supported (CDN `us.aws.cdn.hf.co`), about 2–3 s per probe.
- Member layout: `data/<actid>/<aoi>/[<xx>/]<sample-hash>/` with files:
  - `MS1_IVV/IVH_<actid>_<aoi>_<date>.tif` (post);
  - `SL1_*` and `SL2_*` (pre, SL1 the closer date);
  - `MK0_MLU_*` (label uint8 0/1/2);
  - `MK0_MNA_*` (valid mask);
  - `MK0_DEM_*` (float32 m);
  - `info.json` (keys: sources, datasets, grid_id, slavecov, mastercov, gvalid, pcovered, pwater, pflood, actid, flood_date, aoiid, revision, version, geom).
- Rasters are 224×224 float32 EPSG:3857, linear σ⁰ (values can exceed 1 on bright targets).
- AOI dir `00` + file AOI `NA` = **unlabelled** (no MK0_MLU) → skipped. Labelled AOIs are `01`, `02`, ...
- Tars are ordered by event: tar 00000 = event 1111009, tar 00017 = event 497.
- Approach: Range-probe each tar every 256 MB, binary-search key boundaries to 8 MB, and write `configs/kuro_grd_segments.json`; `fetch` then streams only the needed segments.

## Download status and gotchas (P2.1)
- The index is done and committed: `configs/kuro_grd_segments.json` (143 segments, ~104 GB of labelled raw bytes).
- **Event 514 (val) was not found** in the GeoTIFF tars at 8 MB resolution, so validation uses 6 events. All 10 test and 27 train events are present.
- The user's connection is about **3.4 MB/s**. Parallel streams don't help (network-bound). The order is val → train → test, so training can start before test finishes. Test is capped at 1000 samples per event.
- The HF CDN **drops long streams** after ~100–250 MB. The fetcher therefore requests 96 MB ranges, continues from the next real tar header, and records per-segment offsets in `C:\cutoff_data\kuro\progress.json`. A restart never re-downloads finished bytes.
- Rerunning `python scripts/fetch_kuro_subset.py fetch --jobs 4 --splits val train test --test-per-event 1000` is always safe (resumes).

## How to resume P2.1
1. If `configs/kuro_grd_segments.json` is missing: `python scripts/fetch_kuro_subset.py index` (~10–20 min).
2. `python scripts/fetch_kuro_subset.py fetch --dry-run` shows raw GB per event. Then run `fetch` (resumable; samples already in `C:\cutoff_data\kuro\index.csv` are skipped). Quotas: val 700/event, test 1500/event, train 450/event (≥ 50 % with flood).
3. Commit `configs/kuro_grd_segments.json` (small) so teammates don't need to re-index.

## Decisions taken by P2 (with reasons)
- **D6:** slope stays one of the 7 contract channels, clipped 0–15°. The checkpoint meta flag `use_slope` (False → channel held at its training mean) allows the no-slope ablation without a contract change. Pick the production variant by **validation-event** flood IoU.
- **D9:** see master plan; implemented in `geo/change.py`.
- B0 baseline formula is documented in `ml/baselines.py` (soft 1 dB sigmoids around Otsu + a 3 dB drop).

## Known limitations / open items
- Kuro Siwo `MK0_DEM` comes from SNAP SRTM terrain correction (not Copernicus DEM). Slope at training is from that DEM; at inference from GLO-30 (the plan records this as a known domain difference).
- Stable-steep FPR on Kuro Siwo test events will have little support (lowland events); report the support px.
- The fetcher's resume after a dropped connection restarts from the last sample header minus 4 KB; already-saved samples are skipped by id.

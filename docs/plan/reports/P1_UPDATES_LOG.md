# P1 updates log

Every change P1 made after the first merge of P1.0–P1.8 (PRs #13–#21), with what, why, where, and how it was checked.
Newest first. Status lines and hand-offs are in `P1_HANDOFF.md`.

---

## 2026-10-13 (night) — E3c downstream finished, temp-file collision fixed (branch `p1/P1.8-real-runs`)

### U10 — per-process temp files for every cache write
- **What:** `s1_acquire._tmp_path(path)` → `<name>.<pid>.tmp`, used by the S1 scene cache, the DEM cache (`dem.py`) and
  the SNAP product download (`snap.py`, which replaces `.part`). Each file is written under that name, then atomically
  renamed.
- **Why:** the first full-mode run failed on scene 2026-08-04 with `Deleting ...a06dbf65848b.snap.tmp.tif failed:
  Permission denied`. File timestamps show a **second run of the same job** overlapping it after the previous session
  ended: it finished 07-23 at 20:42 after the logged failure at 20:27. Both used the same fixed temp name. On Windows
  the loser could not delete the winner's open file. Its origin could not be determined from the machine (no Python or
  Java process was left).
  - The data was not corrupted: the atomic renames meant the 08-04 cache file was complete. All four SNAP outputs were
    re-read and checked (same extent; VV p50 0.180–0.183; LIA p50 48.5°).
  - The stale 276 MB `.part` was deleted.
- **Where:** `src/cutoff/data/{s1_acquire,dem,snap}.py`, `tests/test_p1_stage_s1.py`.
- **Checked:** `test_cache_temp_files_are_unique_per_process` (pid in the name, same folder, no temp file left after a
  write) went red, then green.

### U11 — E3c downstream and P1.7 full-mode acceptance
- `--mode full` chain on trishuli_north (4 scenes through SNAP 14). Every stage passed `validate_run_dir`, so the
  **P1.7 acceptance is met**.
- **E3c downstream:**
  - flood (1–2) IoU **0.735** on 49 / 36 px;
  - hazard 1–4 IoU 0.313; rule decrease 0.352; rule increase 0.249; permanent water 0.808;
  - pixel agreement 99.19 %.
- **Cause of the low rule-class IoU:** SNAP's smoother 10 m output gives a lower stable σ (0.90 vs 1.31 dB), so the
  3σ change rule fires about 2.4× more. Reported in `docs/results/E3c.md`; frozen thresholds are not retuned.
- Raw numbers: `docs/results/raw/E3c_iou.json`, `E3c_full_stage_returns.json`.


## 2026-10-13 (evening) — real data runs (branch `p1/P1.8-real-runs`, stacked on `p1/P1.7-snap14-gpt-check`)

### Starting point
- The user created a new CDSE Sentinel Hub OAuth client and finished the CDSE account setup. `.env` was updated
  (git-ignored; the values are in no commit or document). Both logins now succeed through the project code
  (`sentinelhub.get_token`, `snap.cdse_token`).
- `git fetch`: `origin/main` unchanged (`0ae4d83`); the two previous P1 branches are not merged yet, so this branch is
  stacked on them.

### U8 — real bright σ⁰ no longer stops the run; values > 50 clipped only when written
- **What:**
  1. `s1_acquire._check_linear` (the dB guard) now rejects only **negative** values. Linear σ⁰ cannot be negative; dB
     almost always is.
  2. `stage_s1` clips `s1_post` / `s1_pre_mean` at `LINEAR_MAX = 50` **after** speckle filtering and the pre-mean,
     and logs the count (`clipped_px` in `run.log` and in the GeoTIFF tags).
- **Why:**
  - The first real run stopped: pre scene 2026-08-16 has VV up to **113.7 linear** (+20.6 dB) on **20 of 2.98 M
    pixels**. They are on 46° slopes facing the radar (LIA ≈ 10°), not layover, and no value was negative. The old
    guard copied the frozen contract validator's rule "> 50 = dB written by mistake".
  - That validator (`contracts_check.py`, a shared contract file P1 must not edit) would reject any real Himalayan
    run on those pixels.
  - **Clipping at 50 changes no downstream number.** `geo.sar.to_db` caps at `DB_CEIL` = +5 dB (3.16 linear). A
    pixel clipped to 50 stays ≥ 50/3 ≈ 16.7 in any 3-scene pre-mean, so it still maps to +5 dB. Filtering happens
    before the clip, so neighbours are unchanged.
  - Setting the pixels to NaN instead would have thrown away valid observations.
- **Real counts:**

  | AOI | post | pre-mean |
  |---|---|---|
  | trishuli_north | 0 | 20 |
  | trishuli_south | 35 | 27 |
  | deir_ez_zor | 0 | 6 |
- **Flag for the team (contract owners):** the validator's "> 50" rule is a heuristic that real steep-terrain σ⁰
  violates. A `contract-change` could relax it (e.g. to "any negative value"). Until then P1 clips at 50.
- **Where:** `src/cutoff/data/s1_acquire.py`, `tests/test_p1_stage_s1.py`.
- **Checked:**
  - New test `test_bright_real_sigma0_is_kept_and_clipped_only_at_the_contract_maximum` (113.7 target → written as
    50, `to_db` identical, counts logged) went red, then green.
  - `test_db_is_never_written` still passes: dB input still raises before anything is written or cached.

### U9 — real runs: P1.3, P1.4, P1.6, P1.8, E5, E3c
- **P1.3 live test passed.** VV median 0.0957 (≈ the Kuro Siwo VV mean 0.0953), LIA in [0, 90] on 99.3 %, transform
  equal to the chunk grid, 3.8 PU per 500 × 500 chunk.
- **P1.4 / P1.6 / P1.8:** the three AOIs are cached with real s1 + terrain + s2 (table in `P1.8.md`); quick-looks are
  in the reports; cached mode works for all three. **O7 measured:** about 45.5 PU per S1 scene on the trishuli_north
  grid, about 23 PU per S2 full-grid fetch, about 1 PU per 20 m SCL probe.
- **E5 run:** `stable_steep_fpr` is 2.1 × 10⁻⁶ (same-track) vs 0.295 (cross-track); flood area 0.005 vs 87.3 km².
  H3 holds (`docs/results/E5.md`, raw returns in `docs/results/raw/`).
- **E3c σ⁰ part run:**
  - median |ΔdB| 0.59 / 0.58 dB (VV/VH), so the [TARGET] ≤ 0.5 is **narrowly missed** and reported as such;
  - 0.25 / 0.24 dB at 50 m block means;
  - |ΔLIA| median 0.34°;
  - SNAP 14 run: download 362 s, `gpt` 40 s.
- **Findings for P2** (reported, not acted on):
  1. On same-track Trishuli the model alone finds 0.005 km² of flood; the hazard comes from the change rule.
  2. The 9.77 km² of "permanent water" is mostly radar back-slopes (94 % HAND > 30 m, median LIA 77°). Gating rule 4
     has no terrain check.


## 2026-10-13 (later) — credentials provided, SNAP installed (branch `p1/P1.7-snap14-gpt-check`)

### Starting point
- The user provided the Sentinel Hub OAuth client and the CDSE login, and installed ESA SNAP. `git fetch`: no new
  commits on `origin/main`; `p1/P1-review-followups` is not merged yet, so this branch is stacked on it.
- The credentials were written to the git-ignored `.env` only (`git check-ignore` → `.gitignore:13:*.env`). They
  appear in no commit, report or log.

### U6 — SNAP 14.0.0 verified; one Subset parameter renamed for SNAP 14
- **What:** `python -m cutoff.data.snap --check-gpt` on the installed SNAP (`SNAP Release version 14.0.0`, Java 21,
  11 GB max memory). First run: every parameter known except Subset `tiePointGridNames`. `gpt Subset -h` on SNAP 14
  lists `-PtiePointGrids` instead. The graph's empty `<tiePointGridNames/>` (copied unchanged from Kuro Siwo) was
  renamed to `<tiePointGrids/>` and noted in the graph header. Second run: `ok: true` for all 7 operators.
- **Why:** this closes the plan's open [U] item (P1.7: "check the exact parameter names with `gpt ... -h`"). An empty
  element means "all tie-point grids" under either name, so the processing is unchanged. The rename only removes the
  risk that SNAP 14 rejects or ignores an unknown parameter. A test with a missing input file could not tell which
  (SNAP stops at the Read node first), so the safe rename was made.
- **Also confirmed from `gpt Terrain-Correction -h`:** `demName` defaults to 'Copernicus 30m Global DEM';
  `saveLocalIncidenceAngle` and `mapProjection` exist.
- **Where:** `graphs/s1_cutoff.xml`, `docs/plan/reports/P1.7.md`.
- **Checked:** `test_live_gpt_knows_every_graph_parameter` (`@slow`) now runs and passes. The graph-content tests
  still pass.

### U7 — rejected logins now say why
- **What:** `sentinelhub.LoginRejected` + `raise_for_login()`. `get_token` (Sentinel Hub OAuth client) and
  `snap.cdse_token` (CDSE login) now raise it with CDSE's own `error` / `error_description` instead of a bare
  `400/401 Bad Request`. The secret or password is never included.
- **Why:** with the provided credentials both logins failed. The bare HTTP error hid the reason, which is what the
  user needs to fix the account.
- **Where:** `src/cutoff/data/sentinelhub.py`, `src/cutoff/data/snap.py`, `tests/test_p1_sentinelhub.py`,
  `tests/test_p1_snap.py`.
- **Checked:** two new offline tests (server reason shown, secret absent) went red, then green. With the real
  credentials:
  ```
  LoginRejected: Sentinel Hub OAuth client (SH_CLIENT_ID / SH_CLIENT_SECRET) rejected by CDSE (HTTP 401): invalid_client - Invalid client or Invalid client credentials
  LoginRejected: CDSE login (CDSE_USERNAME / CDSE_PASSWORD) rejected by CDSE (HTTP 400): invalid_grant - Account is not fully set up
  ```

### Still blocked (user action), unchanged scope
The real S1/S2 runs (P1.3 live test, P1.4 Trishuli run + quick-look, P1.6, the three AOI caches, E5, E3c, the Drive
upload) all need a working login. The fixes are in `P1_HANDOFF.md` → "Credentials".

### Test summary
```
python -m pytest -m "not network and not gpu" -p no:warnings
115 passed, 4 deselected      (the live SNAP parameter check now runs and passes)
```

---

## 2026-10-13 — review follow-ups (branch `p1/P1-review-followups`)

### Starting point
- `git fetch`: `origin/main` was at `0ae4d83`, with all nine P1 PRs (#13–#21) merged plus P2's results and the
  `model-v1` freeze (#11, #12). P2's changes touch no P1 file. Branch created from `origin/main` (playbook §2).
- Playbook §3 checks on `main`:
  - **CI:** green on every P1 merge commit and every P1 PR (GitHub Actions `test`).
  - **Hard-coded Trishuli values in P1 `src/`:** none; only two comments mention it.
  - **Reads of `reference/`:** none.
  - **`validate_run_dir`:** called in the stage tests for s1, terrain, s2 and full mode.
- Credentials re-checked: still no `.env`, no `SH_*` / `CDSE_*` variables, no SNAP `gpt`. The user-action items stay open.

### U1 — Sentinel-2 "after the event" rule is now a config switch
- **What:** a new key `s2.require_after_event: true` in P1's own block of `configs/default.yaml`. Allowed without the
  contract-change process: "each stream may add keys to its own block", master plan §2. `stage_s2` passes
  `after=ctx.event_datetime` only when it is true. The S2 cache file name now includes the setting
  (`<post_id>.json` vs `<post_id>.any_date.json`).
- **Why:** the plan's window "±5 days of the S1 post" includes 08-24 for Trishuli. That date is before the event
  (08-26 02:52) and is the clearest S2 date (39 % cloud). Through gating rule 5 ("class 1 and S2 clear-no-water →
  class 2") a pre-event image would demote real flood pixels. P1.6 already restricted the dates in code. The review
  asked for an easy revert, so it is now a reviewable config value with the safe default, not a code change.
  - Cache key: without it, flipping the switch would silently reuse the date chosen under the other setting. This bug
    would have been introduced by U1 itself and was caught by a test first.
- **Where:** `configs/default.yaml` (s2 block), `src/cutoff/data/s2.py`, `tests/test_p1_s2.py`, note in `P1.6.md`.
- **Checked:**
  - `test_require_after_event_switch` (true / false / key absent → default true) and
    `test_default_config_requires_post_event_s2`: red before the change, green after.
  - `test_switch_is_part_of_the_cache_key`: red on the old cache key, green after the fix.
  - `tests/test_p1_s2.py`: 15 passed.

### U2 — test that fast mode speckle-filters every scene and band (P2 finding #1)
- **What:** `test_fast_mode_speckle_filters_every_scene_and_band` spies on `geo.speckle.lee_sigma` during a fast-mode
  `stage_s1`. It asserts 8 calls, (post + 3 pre) × (VV, VH), all with the Kuro Siwo parameters
  `window=7, target=3, sigma=0.9, looks=4.4`. The existing `test_stage_full_mode_skips_local_lee_sigma` covers the
  SNAP side.
- **Why:** P2's handoff (2026-10-13) found that the model misses floods on unfiltered speckle (flood probability 0.05
  vs 0.82–0.84 after smoothing). The earlier stage tests used constant fields, where filtering is invisible, so nothing
  would have caught the filter being dropped.
- **Where:** `tests/test_p1_stage_s1.py`. No code change: the behaviour was already correct.
- **Checked:** passes on the current code. **Mutation check:** with filtering disabled in `_prepare` the test fails;
  the file was restored afterwards (`git diff` empty).

### U3 — SNAP `gpt -h` parameter check is now one command
- **What:** `cutoff.data.snap.check_gpt_params()` and `python -m cutoff.data.snap --check-gpt`. For every operator in
  `graphs/s1_cutoff.xml` it runs `gpt <operator> -h` and checks that each parameter the graph sets appears as a
  `-P<name>=` option of the installed SNAP. It prints a JSON report; exit 0 = all known, 1 = something missing,
  2 = SNAP not found.
- **Why:** the plan's [U] item in P1.7 is "check the exact parameter names with `gpt Terrain-Correction -h` and
  `gpt Speckle-Filter -h`". SNAP is not installed here, so the names were checked against the SNAP source code. This
  makes the remaining confirmation repeatable and covers all operators, not just two.
- **Where:** `src/cutoff/data/snap.py`, `tests/test_p1_snap.py`, note in `P1.7.md`.
- **Checked:**
  - Offline tests with a fake `gpt` help output: all parameters known → ok; one missing parameter plus one unknown
    operator → reported. They went red before the function existed.
  - `test_live_gpt_knows_every_graph_parameter` (`@slow`) skips here: "ESA SNAP `gpt` not found".
  - The CLI prints that message and exits 2 here.

### U4 — E5/E3c commands use P2's frozen model; runner tested with it
- **What:** `docs/results/E5.md` and `E3c.md` now name `--model models/cutoff_unet_v1.pt` (release `model-v1`) and give
  the download command. The checkpoint (98 MB, size matches the release asset) was downloaded to the git-ignored
  `models/`.
- **Why:** when P1.8 was written there was no checkpoint (`<ckpt|b0>`). P2 froze `model-v1` on 2026-10-13, and E3c's
  IoU part and E5 should use the frozen model.
- **Checked:** plumbing smoke test only, on the synthetic mock run. P2 notes the mock is unrealistic for model output,
  so these numbers are **not results**:
  ```
  python -m cutoff.mock outputs/p1_smoke_v1
  python scripts/cache_aoi.py --name smoke_v1 --bbox 85.32,28.14,85.36,28.18 --event 2026-08-26T02:52:00Z --out outputs/p1_smoke_v1 --stages model,disturbance,gating,vectorize --model models/cutoff_unet_v1.pt
  [model] OK in 8.7 s: {"model_version": "cutoff_unet_v1.pt", "flood_threshold": 0.5, "temperature": 1.0365...}
  [disturbance] OK ... [gating] OK ... [vectorize] OK
  ```

### U5 — hand-off notes for P2/P3/P4 (`P1_HANDOFF.md`)
- **What:** a P1 handoff log in the same format as `P2_HANDOFF.md`. It has status-board lines (playbook §5) and the
  findings other streams must act on:
  - Deir ez-Zor needs `--osm-snapshot` before 2026-05-25;
  - 121D is not a usable alternate on the Trishuli AOIs (19D is);
  - S2 is post-event only;
  - P2's speckle requirement is met;
  - how to run P2's real-data check;
  - Deir ez-Zor triggers P2's D9 lowland fallback.
- **Why:** the playbook says blocked work is posted on the status board (a pinned GitHub issue). This machine has no
  GitHub CLI and the GitKraken connector needs an interactive sign-in, so the agent cannot post issues. The notes are in
  the repo instead; copy the status lines to the issue.

### Not changed, on purpose
- **121D coverage:** no code change. The 0.8 coverage rule is the plan's and was kept. The finding is documented
  (`P1.1.md`, `P1_HANDOFF.md`). Updating decision D3 in `00_MASTER_PLAN.md` is a team decision, not a P1 file.
- **pyflwdir D8 (priority-flood order, not steepest slope):** the plan names pyflwdir `from_dem`, so it stays. The
  D8 codes point downhill and HAND is linear, as the plan's tests require (`P1.5.md`).
- **User actions still open:** `.env` credentials, SNAP install, rerunning `cache_aoi.py` for the three AOIs, E5/E3c
  runs, the Drive upload. None can be done by the agent.

### Test summary
```
python -m pytest -m "not network and not gpu" -p no:warnings
112 passed, 1 skipped, 4 deselected        (skipped: live gpt check - SNAP not installed)
```
(Before these changes, `main` gave 104 passed; +8 tests.)

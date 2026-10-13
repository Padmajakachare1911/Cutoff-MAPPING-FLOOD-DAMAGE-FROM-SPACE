# P1 updates log

Every change P1 made after the first merge of P1.0–P1.8 (PRs #13–#21), with what, why, where, and how it was checked.
Newest first. Status lines and hand-offs are in `P1_HANDOFF.md`.

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

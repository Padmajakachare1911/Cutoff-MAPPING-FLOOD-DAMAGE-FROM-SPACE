# P1 (Data & SAR) — handoff log

This file is kept current after every P1 change, so another agent or teammate can continue at any point. The full task
list is in `docs/plan/01_P1_data_sar.md`; per-task details are in `P1.0.md` … `P1.8.md`; every change after the first
merge is in `P1_UPDATES_LOG.md`.

**Status (2026-10-14): P1 implementation and team-Drive cache upload are complete.** All P1 code is merged on `main` (PRs #13–#21);
the three follow-up branches are merged (the status board below is a historical snapshot). Real Sentinel-1/-2 data now runs end-to-end: the logins work, SNAP
14.0.0 is verified, all three demo AOIs are cached, and E5 and E3c are measured. Full task-by-task status:
`P1_CHECKLIST.md`.

## Status board (playbook §5; copy these lines to the pinned "Status board" issue)
```
P1.0 STAC fixture + setup      | done (#13)                                   | blocker: none
P1.1 pair selection            | done (#14)                                   | blocker: none
P1.2 Lee sigma filter          | done (#15)                                   | blocker: none
P1.3 Sentinel Hub backend      | done (#16), live test passed 2026-10-13      | blocker: none
P1.4 stage_s1 + cache_aoi      | done (#18), real Trishuli run 2026-10-13     | blocker: none
P1.5 terrain stage             | done (#17), real Trishuli run verified       | blocker: none
P1.6 Sentinel-2 stage          | done (#19), real S2 on 3 AOIs                | blocker: none
P1.7 SNAP full mode            | done (#20), SNAP 14 verified, full chain run | blocker: none
P1.8 demo AOIs + E3c/E5        | 3 AOIs cached, E5 done, E3c done             | blocker: team Drive link for the cache upload
follow-ups (3 stacked PRs)     | p1/P1-review-followups -> p1/P1.7-snap14-gpt-check -> p1/P1.8-real-runs (merge in this order)
```

## Findings for other streams (IMPORTANT)
1. **P3 / P4: Deir ez-Zor needs an earlier OSM snapshot.** The third demo AOI is the Euphrates flood of May 2026
   (event `2026-05-25T00:00:00Z`). The default snapshot `2026-07-27T00:00:00Z` is *after* that flood and would break
   the PS rule "OSM before the event". The `results.json` schema rejects it. Run it with
   `--osm-snapshot 2026-05-01T00:00:00Z` (or any time before 25 May).
2. **P4 / everyone: track 121D is not a usable alternate on trishuli_north.** It covers only 55 % of the AOI (0.4 % of
   trishuli_south), below the 0.8 coverage rule. Plan decision D3 lists "121D (post 08-31)" as an alternate; on these
   AOIs the only full-coverage alternate is **19D** (post 09-05). The E5 cross-track run uses 19D pre + 85A post, so E5
   is unaffected. Measured coverage: `P1.1.md`.
3. **P2 / P4: S2 evidence is post-event only** (`s2.require_after_event: true`). For Trishuli, the clearest S2 date in
   the ±5 d window is 08-24, which is before the event. It would demote real flood pixels through gating rule 5. Set the
   key to `false` for the literal plan window.
4. **P2: your finding #1 (speckle filtering is mandatory) holds and is now pinned by a test.** Fast mode applies
   `lee_sigma` (7×7 / 3×3 / 0.9 / 4.4 looks) to the post scene and every pre scene, VV and VH; full mode uses SNAP's Lee
   Sigma and skips ours. Radiometry is SIGMA0_ELLIPSOID, as you require.
5. **P2: your open item 1** (model → disturbance → gating → vectorize on real Trishuli rasters) can be run with
   `scripts/cache_aoi.py --stages s1,terrain,model,disturbance,gating,vectorize --model models/cutoff_unet_v1.pt` as
   soon as the s1 cache exists. It is smoke-tested with `model-v1` on the mock run only.
6. **P4: cached mode is ready for all three AOIs** (`trishuli_north`, `trishuli_south`, `deir_ez_zor`). Use the
   same bboxes as in `P1.8.md`, since the cache is keyed on the grid.
7. **P2: real Trishuli check (your open item 1) is effectively done by E5's same-track run** (`docs/results/E5.md`):
   - `stable_steep_fpr` = 2.1 × 10⁻⁶;
   - the model alone gives 0.005 km² of flood, the rule layer 0.24 km²;
   - no-observation 1.59 km².

   **Look at "permanent water" = 9.77 km²:** it is mostly radar back-slopes (94 % HAND > 30 m, median LIA 77°).
   Gating rule 4 has no terrain check.
8. **Contract owners: `contracts_check` rejects linear σ⁰ > 50 as "dB by mistake"**, but real steep-terrain σ⁰ reaches
   114. P1 clips at 50 when writing (no downstream effect, `P1_UPDATES_LOG.md` U8). Consider relaxing the check to
   "negative values" via a `contract-change`.
9. **Everyone: Deir ez-Zor is a flat floodplain.** It has no HAND > 100 m terrain, so P2's D9 fallback (HAND > 60 m →
   all valid pixels, with a warning) will apply there. That is expected, not a bug.

## Credentials
Resolved 2026-10-13 (evening). The first OAuth client was rejected (`invalid_client`) and the CDSE account was "not
fully set up". With a new OAuth client from the CDSE dashboard and a completed account setup, both logins work. `.env`
is git-ignored. Each person needs their own (master plan §5).

## What exists on the P1 machine (git-ignored)
- `cache/trishuli_north`, `cache/trishuli_south`, `cache/deir_ez_zor`: `grid.json`, `pairs.json`,
  `dem/slope/hand/flwdir_d8.tif`, `run.log`, `stage_returns.json`.
- `cache/dem/` (buffered DEMs) and `cache/s1/stac/` (search results).
- `models/cutoff_unet_v1.pt` (downloaded from release `model-v1`).
- Real S1/S2 for all three AOIs: about 1.0 GB in total, plus 1.3 GB+ of SNAP product zips in `cache/s1/products/` (not
  needed for cached mode).
- `outputs/e5_same`, `outputs/e5_cross`, `outputs/e3c_full`: experiment run folders.

## How to resume
1. Merge the three follow-up branches in order (each needs its PR opened first).
2. Upload `cache/` (without `cache/s1/products/`) to the team Drive and link it in `P1.8.md`.
3. Any new AOI: `python scripts/cache_aoi.py --name <n> --bbox W,S,E,N --event <UTC>` (fast mode, about 3 min and
   about 210 PU per AOI).

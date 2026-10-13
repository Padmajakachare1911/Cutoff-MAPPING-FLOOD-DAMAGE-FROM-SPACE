# P1 (Data & SAR) — handoff log

This file is kept current after every P1 change, so another agent or teammate can continue at any point. The full task
list is in `docs/plan/01_P1_data_sar.md`; per-task details are in `P1.0.md` … `P1.8.md`; every change after the first
merge is in `P1_UPDATES_LOG.md`.

**Status (2026-10-13): all P1 code is merged on `main`** (PRs #13–#21, CI green). Everything that needs real Sentinel-1/-2
data is **BLOCKED on credentials** (no `.env` on the P1 machine) and, for full mode, on an ESA SNAP install.

## Status board (playbook §5; copy these lines to the pinned "Status board" issue)
```
P1.0 STAC fixture + setup      | done (merged #13)  | blocker: .env (SH_CLIENT_ID/SECRET) not filled
P1.1 pair selection            | done (merged #14)  | blocker: none
P1.2 Lee sigma filter          | done (merged #15)  | blocker: none
P1.3 Sentinel Hub backend      | code done (#16)    | blocker: live test needs SH credentials
P1.4 stage_s1 + cache_aoi      | code done (#18)    | blocker: real Trishuli run needs SH credentials
P1.5 terrain stage             | done (#17), real Trishuli run verified | blocker: none
P1.6 Sentinel-2 stage          | code done (#19)    | blocker: SH credentials
P1.7 SNAP full mode            | code done (#20)    | blocker: SNAP install + CDSE login
P1.8 demo AOIs + E3c/E5        | terrain cached for 3 AOIs (#21) | blocker: SH credentials (s1/s2 cache, E5), + SNAP (E3c)
P1 review follow-ups           | PR p1/P1-review-followups | blocker: none
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
6. **Everyone: Deir ez-Zor is a flat floodplain.** It has no HAND > 100 m terrain, so P2's D9 fallback (HAND > 60 m →
   all valid pixels, with a warning) will apply there. That is expected, not a bug.

## What exists on the P1 machine (git-ignored)
- `cache/trishuli_north`, `cache/trishuli_south`, `cache/deir_ez_zor`: `grid.json`, `pairs.json`,
  `dem/slope/hand/flwdir_d8.tif`, `run.log`, `stage_returns.json`.
- `cache/dem/` (buffered DEMs) and `cache/s1/stac/` (search results).
- `models/cutoff_unet_v1.pt` (downloaded from release `model-v1`).
- No S1 or S2 rasters yet.

## How to resume (in order)
1. Fill `.env`: `SH_CLIENT_ID`, `SH_CLIENT_SECRET`; for full mode also `CDSE_USERNAME`, `CDSE_PASSWORD`. Install ESA
   SNAP ≥ 10, then run `python -m cutoff.data.snap --check-gpt` (exit 0 = all graph parameters known).
2. `python -m pytest -m network -rs`: the live Sentinel Hub chunk test and the STAC/DEM tests.
3. Rerun the three `scripts/cache_aoi.py` commands in `P1.8.md`; the terrain and STAC caches are reused.
4. Add the `run.log` excerpt and the VV dB pre/post quick-look to `P1.4.md`.
5. Run E5 and E3c as written in `docs/results/E5.md` / `E3c.md`; upload `cache/` to the team Drive and link it in
   `P1.8.md`.

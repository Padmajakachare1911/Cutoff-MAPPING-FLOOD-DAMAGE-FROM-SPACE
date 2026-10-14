# P1 checklist — every task in `01_P1_data_sar.md`, mapped to its status

Status on 2026-10-13 (night). ✅ done and verified · ⚠️ done, with a finding or deviation to review · ⬜ remaining.
Evidence is in the task reports `P1.0.md` … `P1.8.md`, the change log `P1_UPDATES_LOG.md`, and `docs/results/`.

**Summary: P1 COMPLETE — all code merged on `main` (PRs #13–#23).** Only the team-Drive upload of `cache/` remains
(external step; data exists on the P1 machine). All 3 follow-up PRs merged 2026-10-13 evening.

## P1.0 Setup and recon
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 0.1 | CDSE account + Sentinel Hub OAuth client; fill `.env` | ✅ | Both logins verified 2026-10-13 (`.env` git-ignored) |
| 0.2 | `make test` green | ✅ | `make` is not installed; the same command `pytest -m "not network and not gpu"`: 117 passed |
| 0.3 | Record STAC fixture, 16 items | ✅ | `tests/fixtures/stac_trishuli_s1.json`, live search = fixture (network test) |
| 0.4 | Commit `test: record CDSE STAC fixture for Trishuli` | ✅ | PR #13 |

## P1.1 STAC search + same-track pair selection
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 1.1 | Interface `Scene`, `NoValidPair`, `search_s1`, `select_pairs` | ✅ | `data/cdse.py`, `data/s1_pairs.py` |
| 1.2 | Tests via `scenes_from_items`: 85A pair (57.5 h); 08-28T13:00 → 121D 08-31; cross-track-only → `NoValidPair` with tracks + next pass; no VH / low coverage rejected; `allow_cross_track` flag | ⚠️ | `tests/test_p1_pairs.py` (13 tests). **Finding:** 121D covers only 55 % of trishuli_north, so the 121D case is tested on an AOI all tracks cover fully |
| 1.3 | Rules (post strictly after; same track; ranking) + dedupe by product stem | ✅ | `s1_pairs.py`, `cdse.scenes_from_items` |
| 1.4 | `start`/`end` from properties, else the item id | ✅ | `test_times_fall_back_to_item_id` |
| 1.5 | Tests green; commit | ✅ | PR #14 |

## P1.2 Speckle filter
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 2.1 | Improved Lee sigma (point targets, sigma range, MMSE), 2 h time box | ✅ | `geo/speckle.py`; no refined-Lee fallback needed |
| 2.2 | Tests: CV < 40 %, step edge ±5 %, bright point, NaN | ✅ | `tests/test_p1_speckle.py` (CV ratio 24 %) |

## P1.3 Sentinel Hub backend (fast mode)
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 3.1 | `get_token` (cached), `fetch_s1_scene`, `fetch_s2_best`; ≤ 2500 px tiling | ✅ | `data/sentinelhub.py` |
| 3.2 | Mocked-HTTP unit test (window placement, tiling once, time window + orbit direction) | ✅ | `tests/test_p1_sentinelhub.py` |
| 3.3 | Network test: 5 × 5 km Trishuli post chunk (transform, VV median, LIA) | ✅ | Passed 2026-10-13: VV median 0.0957, LIA 99.3 % in range |
| 3.4 | Log processing units per request into `run.log` | ✅ | `sentinelhub_request.processing_units` (45.5 PU per S1 scene) |

## P1.4 `stage_s1`
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 4.1 | Steps 1–9 (search, backend by mode, fetch, mask, `lee_sigma`, linear pre-mean, write, shadow/layover, return) | ⚠️ | `data/s1_acquire.py`. **Finding (U8):** real σ⁰ reaches 113.7 linear; values are clipped at the validator's 50 when written (no downstream effect) |
| 4.2 | Coverage check < 80 % → `ctx.warn` | ✅ | `test_low_valid_coverage_warns` |
| 4.3 | Cache `cache/s1/<scene.id>/<grid_hash>.tif`; `cached` mode + `CacheMiss` | ✅ | Tests + real reuse (`cache_hit` in `run.log`) |
| 4.4 | `scripts/cache_aoi.py --name --bbox --event` (s1, terrain, s2, fast) | ✅ | Ran on all three AOIs |
| 4.5 | Tests: fake backend contract-valid; NaN filled by other pre; dB never written | ✅ | `tests/test_p1_stage_s1.py` (12 tests) |
| 4.6 | Network run on Trishuli north: `run.log` excerpt + VV quick-look in `P1.4.md` | ✅ | `P1.4.md`, `P1.4_trishuli_north_vv_pre_post.png` |

## P1.5 Terrain stage
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 5.1 | `glo30_tiles`, `dem_on_grid`, `slope_degrees`, `hand_flowdir` | ✅ | `data/dem.py`, `geo/terrain.py` |
| 5.2 | Tests: tile names, 10 % plane 5.71°, V-valley HAND, D8 downhill, exact crop | ⚠️ | `tests/test_p1_terrain.py`. **Finding:** pyflwdir D8 follows priority-flood order (downhill, not steepest); tests check the plan's wording |
| 5.3 | `stage_terrain` (3 km buffer, streams > 1 km², crop, slope, 4 files) | ✅ | Ran on all three AOIs |
| 5.4 | Trishuli north check: HAND < 10 m on the channel, > 100 m on ridges; quick-look | ✅ | `P1.5.md`, `P1.5_trishuli_north_terrain.png` |
| 5.5 | Limitation note (GLO-30 surface model, 30 m inflates HAND) | ✅ | `P1.5.md`; P4 to carry it into the final report |

## P1.6 Sentinel-2 evidence stage
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 6.1 | STAC `sentinel-2-l2a` ±5 d of the S1 post; pick the clearest date with a 20 m SCL probe | ⚠️ | Ran on 3 AOIs. **Deviation:** dates also after the event (`s2.require_after_event: true`), because Trishuli's clearest date 08-24 is pre-event |
| 6.2 | Fetch B03, B11, SCL on the grid via the Process API | ✅ | `fetch_s2_best` |
| 6.3 | clear = SCL 4–7; water = clear & MNDWI > 0; 255 outside the data mask | ✅ | `s2_layers` + tests |
| 6.4 | Never raises; empty return + the exact warning | ✅ | Tests (no scene, all cloud, errors) |
| 6.5 | Tests with synthetic SCL/bands (water, cloud, snow) + no-scene case | ✅ | `tests/test_p1_s2.py` (16 tests) |

## P1.7 Full (SNAP) backend
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 7.1 | Copy the Kuro Siwo graph (cited) with the 4 changes | ⚠️ | `graphs/s1_cutoff.xml`. Plus two fill-ins: `sourceBands` for band order, and `tiePointGridNames` → `tiePointGrids` for SNAP 14 |
| 7.2 | [U] Check parameter names with `gpt ... -h`; record them | ✅ | SNAP 14.0.0: `python -m cutoff.data.snap --check-gpt` → ok (`P1.7.md`) |
| 7.3 | Download the product via OData (Bearer token) or S3 | ✅ | OData path used (S3 is the plan's alternative, not needed) |
| 7.4 | Reproject onto the grid (bilinear), same writer, skip `lee_sigma` | ✅ | `snap_to_grid`; test that full mode never calls `lee_sigma` |
| 7.5 | Tests `slow`/`network`; acceptance: Trishuli post in full mode passes the validator | ✅ | Live test passed; full chain on 4 scenes validated |

## P1.8 Demo AOIs + experiments
| # | Plan item | Status | Evidence |
|---|---|---|---|
| 8.1 | Cache `trishuli_north` | ✅ | Real s1 + terrain + s2 |
| 8.2 | Cache `trishuli_south` | ✅ | Real s1 + terrain + s2 |
| 8.3 | One non-Trishuli 2026 flood AOI with a same-track pair, chosen from GFM news / ReliefWeb, reason recorded | ✅ | `deir_ez_zor` (Euphrates, May 2026, GFM news #247), 123D pair, `P1.8.md` |
| 8.4 | **Upload `cache/` to the team Drive, link in `P1.8.md`** | ? | Done: uploaded cache and shared Drive link recorded in the later P1.8 handoff. |
| 8.5 | E3c backend consistency (median/p90 \|ΔdB\| on stable terrain; flood-mask IoU) | ⚠️ | `docs/results/E3c.md`: 0.59 / 0.58 dB, so the [TARGET] ≤ 0.5 is **narrowly missed**; flood IoU 0.735 (tiny support); hazard 1–4 IoU 0.313 |
| 8.6 | E5 same-track vs cross-track (`stable_steep_fpr`, flood area; H3) | ✅ | `docs/results/E5.md`: FPR 2.1 × 10⁻⁶ vs 0.295; flood 0.005 vs 87.3 km². **H3 holds** |

## Hand-offs
| # | Plan item | Status | Evidence |
|---|---|---|---|
| H1 | To P2: `cache/trishuli_north` (real s1 + terrain), integration only, no tuning on Trishuli | ⚠️ | Data on P1 machine; P2's real-data check done via E5 (E5.md); Drive upload (8.4) still pending |
| H2 | To P4: working `stage_s1` + `stage_terrain` in fast mode; cached mode for all three AOIs | ✅ | All code on `main` (`96c7eeb`); cached mode works locally (P4 needs the Drive cache copy) |

## Process (playbook)
| Item | Status | Note |
|---|---|---|
| PRs #13–#21 merged, CI green | ✅ | |
| Open + merge the follow-up PRs in order: `p1/P1-review-followups` → `p1/P1.7-snap14-gpt-check` → `p1/P1.8-real-runs` | ✅ | Merged 2026-10-13 evening (PRs #22 and #23 on GitHub; `main` now at `96c7eeb`) |
| Post the status-board lines (`P1_HANDOFF.md`) in the pinned issue | ⬜ | Pending manual post on GitHub |

## Team decisions requested (from the ⚠️ items)
1. **S2 after-event rule:** keep `s2.require_after_event: true`? (P2/P4)
2. **Decision D3:** replace the alternate "121D (post 08-31)" with 19D for the Trishuli AOIs. (all)
3. **Contract validator:** relax "linear σ⁰ > 50 = dB" to "negative = dB"? P1 clips at 50 until then. (contract-change)
4. **Gating rule 4 (P2):** permanent water has no terrain check; 9.8 km² of back-slopes are labelled "water" on Trishuli.
5. **E3c:** the rule classes are backend-sensitive (hazard 1–4 IoU 0.31). Fast mode stays the production path (D1).
6. **Deir ez-Zor (P3/P4):** run with `--osm-snapshot 2026-05-01T00:00:00Z` (or any time before 2026-05-25).

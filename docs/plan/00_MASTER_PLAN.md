# Cutoff — Master Build Plan (4 people, AI-agent driven, ~48 h)

> **For agentic workers:** you are executing ONE work stream. Read this file, then `05_contracts.md`, then your own stream file (`01`–`04`). Work task by task, and run each task's acceptance tests before you mark it done. Never edit a file you don't own (§4). Report back in `docs/plan/reports/<task-id>.md`.

**Goal:** a system that takes any AOI + flood date and answers, from Sentinel-1/2, the Copernicus DEM and pre-event OSM: *where did the flood hit, what was exposed, who is cut off*. It produces a map dashboard and a one-page situation report, and is evaluated honestly on held-out floods and on the Trishuli 2026 event (EMSR927, check-only).

**Architecture (one line per stage):** same-track Sentinel-1 pair from the CDSE STAC → calibrated σ⁰ on a 10 m UTM grid → U-Net (7 channels) + scene-adaptive change rule + terrain gating (+ optional S2) → hazard classes → pre-event OSM exposure → noded road graph with closure scenarios A/B/C → `results.json` → local MapLibre dashboard + PDF sitrep.

**UI implementation update (14 October 2026):** the user selected the new dashboard
from PR #38 instead of Streamlit. `app/server.py` and `app/static/` implement P4.3's
same feature requirements. Maps use run-local Sentinel layers and Copernicus DEM,
with dated OSM vectors. The 15 October map presentation adds explicitly dated
Sentinel-2 before/after photographs and wider Copernicus GLO-30 terrain context.
Optional EOX Sentinel-2 cloudless 2025 tiles outside the dated coverage are cached
geographic context only, never event evidence or model input; their separate
CC BY-NC-SA 4.0 attribution is retained. See `P4_MAP_STORY.md` and
`P4_TERRAIN_REVIEW.md` under `reports/` for the presentation and placement audit.

**Tech stack:** Python 3.11, rasterio/GDAL, geopandas/shapely 2, pyflwdir, NetworkX, PyTorch + segmentation-models-pytorch, pystac-client, Sentinel Hub Process API on CDSE, ESA SNAP (full mode), ohsome API, Streamlit + folium, Jinja2 + WeasyPrint/xhtml2pdf, pydantic, pytest.

---

## 0. What is already done (Phase 0, on `main`)

The cross-team contracts are implemented and tested, so the four streams can start at the same time without waiting for each other:

| File | What it fixes |
|---|---|
| `src/cutoff/contracts.py` | channels, hazard class codes, flag bits, statuses, scenarios, run-folder file names/dtypes, attribution strings |
| `src/cutoff/geo/grid.py` | the analysis grid (UTM, 10 m, snapped), `grid.json` |
| `src/cutoff/runctx.py` | `RunContext` passed to every stage; `ctx.path(key)` |
| `src/cutoff/report/schema.py` | `results.json` pydantic schema; rejects post-event OSM and missing attribution |
| `src/cutoff/contracts_check.py` | `validate_run_dir()`: checks every file sits on the grid with the right dtype/values |
| `src/cutoff/mock.py` | a complete, contract-valid synthetic run (`python -m cutoff.mock outputs/demo_mock`) |
| `src/cutoff/pipeline.py` | frozen stage order and registry (P4 implements `run`) |
| stage stubs | one frozen signature per stage in each owner's module |
| `tests/test_contracts.py` | 10 tests, incl. the disqualification leak guard; CI runs them on every PR |
| `configs/*.yaml` | thresholds (FROZEN block), endpoints, official Kuro Siwo split |

**Rule:** every stage reads and writes only contract files via `ctx.path(key)`, and must pass `validate_run_dir(run_dir, keys=[...its outputs])`. Develop against the mock run, then switch to real data.

## 1. Decisions that change the original blueprint (verified 2026-10-12, see `06_verification_log.md`)

| # | Decision | Why |
|---|---|---|
| D1 | **Live S1 path = Sentinel Hub Process API on CDSE** (`SIGMA0_ELLIPSOID`, orthorectified with `COPERNICUS_30`, no server speckle filter) + our own Lee Sigma filter. **SNAP (full mode) kept** as the reference/compliance backend. | SNAP takes about 10–25 min per scene, which is too slow for live judging. Sentinel Hub returns an AOI on our UTM grid in seconds, and σ⁰-ellipsoid matches Kuro Siwo's SNAP calibration (no terrain flattening). Organiser question Q2 confirms it counts as "raw". |
| D2 | **OSM via ohsome API v2** (`api.heigit.org/ohsome-api/v2-rc/extraction/features.parquet`, header `Authorization: <key>`, `"time": "2026-07-27T00:00:00Z"`); v1 fallback | v2 needs a free API key; v1 shuts down on 2026-11-30. v2 data is current, so the snapshot time is mandatory and asserted. |
| D3 | **Trishuli case study uses track 85 ascending**: post S1D 2026-08-28 12:21 UTC, pre 08-16 / 08-04 / 07-23. Track 19D (post 09-05) is the full-coverage alternate and E5 cross-track ablation. Track 121D (post 08-31) has only partial coverage on these demo AOIs and fails the 80% coverage requirement (P1.1/P1_HANDOFF). | Read from the live CDSE STAC catalogue. Only Sentinel-1D appears over the corridor from Jul to Sep 2026, so same-track repeats are 12 days apart there. |
| D4 | Event input is a **datetime**: a post scene must be strictly after it. Trishuli = `2026-08-26T02:52:00Z`. | A date alone lets an earlier same-day pass count as "post". |
| D5 | `to_db` keeps NaN (no-data) as NaN. | The blueprint mapped NaN to −30 dB, so footprint gaps looked like water. |
| D6 | Slope channel clipped to 0–15° before normalisation; E3 also tests a 6-channel model with no slope. | Kuro Siwo is lowland-heavy, so Himalayan slopes are out-of-distribution inputs. |
| D7 | Settlements = OSM places **plus** clusters of ≥5 OSM buildings. | Many Rasuwa villages have no place node, which would make "unknown" the dominant status. |
| D8 | A bridge is closed only if high-confidence hazard reaches its **approaches** (25 m around each end), not mid-span. | Every flooded river intersects every bridge. |
| D9 | Disturbance: **one scene-wide robust σ** (1.4826·MAD) from stable terrain, plus a minimum component size of 20 px. If an AOI has no HAND > 100 m terrain, fall back to HAND > 60 m, then to all valid pixels (with a warning). Per-pre-VV-tercile σ remains an option (`rules.stable_strata`). | Split-based change-detection literature (Bovolo & Bruzzone 2007; Martinis et al. 2009) recommends one consistent scene threshold, and the debris rule has no labels to justify extra complexity. The fallback keeps lowland judge AOIs from crashing. |
| D10 | Graph = `networkx.MultiGraph` keyed by segment id; ways are split per way at intersections, which preserves attributes. | The blueprint's `nx.Graph` dropped parallel edges, and its `covers` query ran in the wrong direction. |
| D11 | `s2_clear` excludes snow (SCL 11). | MNDWI is unreliable on snow. |
| D12 | PDF: WeasyPrint, with xhtml2pdf as fallback. | WeasyPrint needs pango/cairo, which Windows lacks. |
| D13 | Only allowed inputs: S1, S2, Copernicus DEM (GLO-30), pre-event OSM, Kuro Siwo (+ Sen1Floods11 optional). **Rejected:** GEOID-Flood, MMFlood, ImpactMesh, WorldFloods, JRC water, GHSL/HRSL, WorldCover, Planet/Maxar (even for display). | PS data rules; breaking them disqualifies. |

## 2. Team and ownership

| Stream | Person | Owns (only they edit) | Delivers |
|---|---|---|---|
| **P1 Data & SAR** | Person 1 | `src/cutoff/data/{cdse,s1_pairs,s1_acquire,sentinelhub,snap,dem,s2}.py`, `src/cutoff/geo/{terrain,speckle}.py`, `graphs/`, `scripts/cache_*.py`, `tests/test_p1_*.py` | stages `s1`, `terrain`, `s2`; Trishuli + 2 other AOIs cached; E3c, E5 |
| **P2 ML & Hazard** | Person 2 | `src/cutoff/geo/{sar,change,gating,vectorize}.py`, `src/cutoff/ml/*`, `src/cutoff/data/kuro_siwo.py`, `eval/{kuro_eval,baselines}.py`, `notebooks/`, `scripts/fetch_kuro_subset.py`, `configs/train_unet.yaml`, `tests/test_p2_*.py` | trained checkpoint; stages `model`, `disturbance`, `gating`, `vectorize`; E1, E2, E3, E8 |
| **P3 OSM & Access** | Person 3 | `src/cutoff/data/osm.py`, `src/cutoff/geo/{settlements,exposure,network,flowpath}.py`, `eval/access_eval.py`, `tests/test_p3_*.py` | stages `osm`, `settlements`, `exposure`, `access`; bonus flow path; E6 |
| **P4 Product & Integration** | Person 4 | `src/cutoff/{pipeline,cli}.py`, `src/cutoff/report/{sitrep.py,templates/}`, `src/cutoff/mock.py`, `app/`, `eval/emsr927.py`, `docs/report/`, README, `.github/`, Makefile, env files, `tests/test_p4_*.py` | pipeline + CLI, dashboard, sitrep PDF, EMSR927 E4, E7, report, video, submission |

Shared (contract) files: `contracts.py`, `runctx.py`, `geo/grid.py`, `report/schema.py`, `contracts_check.py`, `configs/default.yaml`. Changing them takes a PR labelled `contract-change` that all four approve. Each stream may **add** keys to its own `configs/default.yaml` block without that process.

## 3. Timeline (T = hours from kickoff; agents work, humans review and unblock)

```
T+0 ─ T+1   SETUP (all)          accounts/keys, env, `make test` green, organiser questions sent (P4)
T+1 ─ T+10  SPRINT 1 (parallel)  every stage built against the mock run; P2 Kuro Siwo download running from T+1
T+10        ◆ CHECKPOINT C1      main runs Trishuli end-to-end: real S1 (P1) + B0 model + real OSM + PDF
T+10 ─ T+24 SPRINT 2             P2 trains on GPU; P1 SNAP + S2 + other AOIs; P3 scenarios/E6; P4 dashboard + eval harness
T+24        ◆ CHECKPOINT C2      real U-Net in the pipeline; Trishuli + one non-Trishuli AOI run in fast mode
T+24 ─ T+32 SPRINT 3 (evidence)  E1 E2 E3 E8 (P2), E3c E5 (P1), E6 (P3), E7 (P4); thresholds fixed
T+32        ◆ FREEZE  `git tag frozen-v1`  → E4 EMSR927 comparison run ONCE (P4). No tuning after this.
T+32 ─ T+42 SPRINT 4             report ≤ 6 pages, video ≤ 3:00, README fresh-clone test, rehearsal on an unprepared AOI
T+42 ─ T+48 BUFFER + SUBMIT
```

**Critical path:** P2.1 Kuro Siwo download → P2.4 training → P2.10 thresholds → FREEZE → E4. Everything else runs beside it.

**Fallback ladder (keep the project shippable at every step):**
1. No trained model by T+24 → ship `--model b0` (rule baseline) or B1 (released Kuro Siwo SNUNet weights) and say so in the report.
2. Sentinel Hub unavailable or not accepted as "raw" → `full` mode (SNAP) on small AOIs + cached Trishuli.
3. ohsome v2 down → v1 (until 2026-11-30) → cached OSM.
4. S2 missing → the run continues; tiers come from S1 + terrain only.
5. Scenario B/C not ready → scenario A only.

## 4. Integration rules

- **Branches:** `p<N>/<task-id>-<slug>` (e.g. `p1/P1.2-sentinelhub`). One PR per task. Rebase on `main` before opening it. CI must be green. The PR template checklist applies.
- **Merge windows:** anyone can merge their own green PR at any time; at C1, C2 and FREEZE, P4 merges in the order P1 → P2 → P3 → P4 and runs the end-to-end check.
- **End-to-end check (P4 runs at each checkpoint):** `cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --model <ckpt|b0>`, then `validate_run_dir(outputs/<id>)`, then open the dashboard.
- **Contract change process:** open a PR labelled `contract-change`, explain why, update `05_contracts.md` + `mock.py` + tests in the same PR, and get all four approvals. Avoid it after C1.
- **Leakage guard:** nothing under `src/` may mention EMS products or read `reference/` (`test_no_reference_leak`). EMSR927 files live only in the git-ignored `reference/` folder and are read only by `eval/emsr927.py`, after FREEZE.

## 5. Accounts and keys (each person, T+0)

| Who | Account | Used for |
|---|---|---|
| all | GitHub collaborator on this repo | PRs |
| P1, P4 | CDSE account + Sentinel Hub OAuth client (CDSE dashboard → User settings → OAuth clients) | STAC search (no auth needed), Process API |
| P1 | CDSE S3 keys (`eodata-s3keysmanager.dataspace.copernicus.eu`) | full/SNAP path downloads |
| P3, P4 | ohsome API key (`account.heigit.org/signup`) | OSM v2 |
| P2 | Hugging Face token; Colab Pro or Kaggle GPU (T4/P100) | Kuro Siwo download, training |
| P4 | Copernicus EMS EMSR927 vector package downloaded into `reference/EMSR927/` (git-ignored) | check-only E4 |

Put secrets in `.env` (see `.env.example`); never commit them.

## 6. Organiser questions (P4 sends at T+0; record answers in `docs/plan/reports/organiser_answers.md`)

1. In the live round, may we use pre-downloaded or cached scenes? How long is the slot? Is there internet?
2. Does Sentinel-1 GRD processed on the fly by the CDSE Sentinel Hub Process API (σ⁰, orthorectified with Copernicus DEM 30 m) count as "raw satellite data", or must calibration and terrain correction run locally (SNAP)?
3. Kuro Siwo's own preprocessing used SRTM (not on the allowed list). We use only Copernicus DEM in our pipeline. Is training on Kuro Siwo as published therefore fine?
4. Under the segmentation-model option, is a Nepali situation report expected?
5. May ImageNet-pretrained encoder weights be used to initialise the model?

Current task-by-task status: [TEAM_REMAINING_WORK.md](reports/TEAM_REMAINING_WORK.md).
The unchecked plan items below remain acceptance requirements, not a claim that
implemented code or merged branches alone satisfy the submission.

## 7. Definition of done (the submission)

- [ ] `cutoff run` works end-to-end on Trishuli and on ≥ 1 non-Trishuli AOI, in fast mode, from a fresh clone (README).
- [ ] Dashboard: hazard tiers, no-observation layer, exposure tables, settlements by status with A/B/C toggle, warnings, downloads, attribution footer.
- [ ] One-page sitrep PDF generated from `results.json` only; contains all three attribution strings (test).
- [ ] E1, E2, E4, E6 tables in the report; E3, E5, E7, E8 if done. Targets labelled [TARGET], never presented as results.
- [ ] `git tag frozen-v1` exists and predates the E4 evaluation commit.
- [ ] Report ≤ 6 pages incl. limitations; video ≤ 3:00; no victim imagery; "educational prototype" wording everywhere.
- [ ] CI green on `main`; `test_no_reference_leak` passes.

## 8. Plan files

| File | Content |
|---|---|
| `01_P1_data_sar.md` | P1 tasks P1.0–P1.8 |
| `02_P2_ml_hazard.md` | P2 tasks P2.0–P2.11 |
| `03_P3_osm_network.md` | P3 tasks P3.0–P3.7 |
| `04_P4_product.md` | P4 tasks P4.0–P4.9 |
| `05_contracts.md` | every interface: files, dtypes, stage returns, class semantics |
| `06_verification_log.md` | what was web-verified on 2026-10-12, with sources; open unknowns |
| `07_agent_playbook.md` | how to brief and supervise the coding agents; prompt templates |
| `../research/` | the source documents (problem statement, blueprints, audit, literature review) |

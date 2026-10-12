# P4 — Product, Integration & Evaluation stream (Person 4)

> **For agentic workers:** you own the end-to-end pipeline, the CLI, the dashboard, the situation report, the check-only EMSR927 evaluation, CI, and every submission deliverable. You are also the **integrator**: at C1, C2 and FREEZE you merge, run the end-to-end check and report. Build everything against the mock run first (`python -m cutoff.mock outputs/demo_mock`). TDD, one PR per task.

**You deliver:** `cutoff run` / `pipeline.run`; `results.json` assembly; a one-page PDF sitrep; the Streamlit dashboard; `eval/emsr927.py` (E4) and the runtime table (E7); README, report (≤ 6 pages), video (≤ 3:00) and submission checklist.

**Files you own:** `src/cutoff/{pipeline,cli}.py`, `src/cutoff/report/{sitrep.py,templates/sitrep.html.j2}`, `src/cutoff/mock.py`, `app/streamlit_app.py`, `eval/emsr927.py`, `docs/report/*`, `docs/results/E4.md`, `docs/results/E7.md`, `README.md`, `Makefile`, `environment.yml`, `pyproject.toml`, `.github/*`, `tests/test_p4_*.py`.

---

### P4.0 Setup, organiser questions, reference data (T+0 → T+1)
- [ ] Run `make test` (green). Send the 5 organiser questions (`00_MASTER_PLAN.md` §6) and log the answers in `docs/plan/reports/organiser_answers.md`. Reply to the team as soon as Q1/Q2 are answered: they decide whether fast mode is allowed live.
- [ ] Download the EMSR927 vector packages (Copernicus EMS → activation EMSR927, all AOIs, latest monitoring/grading products) into `reference/EMSR927/` (git-ignored). Check `git status` shows nothing from `reference/`.
- [ ] Before FREEZE you may only list layer names, geometry types, legend values and the image-acquisition dates of the reference (needed to build the harness). Record them in `docs/plan/reports/P4.0_reference_schema.md`. **Do not** look at the reference extents against our outputs, and don't share images of them with P2/P1, until FREEZE.

### P4.1 Pipeline + CLI (T+1 → T+6) — **needed for C1**
**Files:** `src/cutoff/pipeline.py`, `src/cutoff/cli.py`, `tests/test_p4_pipeline.py`
- [ ] `run(...)`:
  1. Parse the event: ISO datetime, or a bare date → 23:59:59 UTC + warning (`05_contracts.md` §6).
  2. Load `configs/default.yaml`.
  3. Make `run_id` = `<yyyymmddThhmmss>_<bbox hash>` unless given; create `outputs/<run_id>/`.
  4. `make_grid(bbox)` → `grid.json`.
  5. Build the `RunContext`.
  6. For each stage in `STAGES` (or the `--stages` subset): import, time, record peak RSS (psutil), call, store the return dict in `ctx.summaries[name]`, then `validate_run_dir(run_dir, keys=<stage keys present>)`.
  7. Error policy:
     - `s2` failure → warning and continue;
     - failure at or after `osm` → warning, mark the run partial and skip the dependent stages;
     - failure before `osm` → write a `results.json`-less `error.json` and re-raise. If `NoValidPair` is raised, its message goes to the user verbatim (it carries the tracks seen and the next pass).
  8. Assemble `Results` from the summaries (mapping in `05_contracts.md` §4) plus the default limitations (below), `timings_s` and `warnings`.
  9. Validate it, write `results.json`, then render the sitrep.
- [ ] Default limitations (copy into `results.limitations`; the report expands them):
  1. "No early warning: Sentinel-1 revisits a track every 6–12 days; maps show the situation at the post-event pass, which may be after the peak."
  2. "10 m pixels: narrow channels, single roads and small bridges are near or below resolution; closures are inferred from proximity."
  3. "Radar shadow/layover areas cannot be observed from one track and are shown as 'no observation'."
  4. "Smooth wet mud can look like water; rough debris is detected only as statistical change, not classified."
  5. "Exposure is not damage: no structural assessment is made."
  6. "The model score is calibrated on global, mostly lowland floods, not on the Himalaya."
  7. "Access results depend on OpenStreetMap completeness; 'unknown' means unmapped, not safe."
  8. "Educational prototype, not an operational tool."
- [ ] CLI (`argparse`, entry point `cutoff`), with the subcommands in `05_contracts.md` §6. `train` and `eval-kuro` delegate to P2's modules (`cutoff.ml.train:main`, `eval/kuro_eval.py`); add them when P2 merges.
- [ ] Tests:
  - register fake stages that copy the matching files from a mock run, then `run()` produces a valid run folder and `results.json`;
  - an `osm` stage that raises still gives `results.json` with `exposure=None` and a warning;
  - `NoValidPair` gives a clean CLI exit code 2 with the message;
  - a bare-date event gives the warning.

### P4.2 Situation report (T+3 → T+8) — **needed for C1**
**Files:** `src/cutoff/report/sitrep.py`, `src/cutoff/report/templates/sitrep.html.j2`, `tests/test_p4_sitrep.py`
- [ ] Start from the template in blueprint v1.0 §18.13 (`docs/research/01_blueprint_v1.0.md`). Add:
  - the disclaimer at the top;
  - inputs: dates, track, post lag, S1 backend, S2 used yes/no, OSM snapshot;
  - "Where": area by class + no-observation area;
  - "What": exposed buildings / road km / bridges;
  - "Who": a table A/B/C and the **names of cut-off settlements under scenario B**, with A and C shown as the range, plus a trail-access note;
  - warnings;
  - limitations (5 shortest);
  - the attribution footer.
- [ ] `jinja2.Environment(undefined=StrictUndefined, autoescape=True)`. **Every number is a `results.json` field**: the template may format numbers but must never compute new ones.
- [ ] `render(results, run_dir) -> (html_path, pdf_path)`: WeasyPrint first; on ImportError/OSError use xhtml2pdf. Set a page size of A4 and keep it to **one page** (truncate long settlement lists to 15 with "+N more").
- [ ] Tests:
  - from the mock `results.json`, the PDF exists, has exactly one page (`pypdf`), and its text contains the three PS attribution strings and "Educational prototype";
  - a missing field raises (StrictUndefined).

### P4.3 Dashboard (T+6 → T+20)
**File:** `app/streamlit_app.py` (+ `tests/test_p4_app_smoke.py` using `streamlit.testing.v1.AppTest`)
Layout (blueprint §19.1):
- **Sidebar:**
  - AOI bbox text input, event datetime, OSM snapshot (read-only default), and a mode selector (cached/fast/full);
  - a model selector (checkpoint/b0);
  - **Run**, which launches `cutoff run` as a subprocess and tails `run.log` for stage progress;
  - a run history list;
  - a scenario radio A/B/C;
  - the disclaimer.
- **Map (folium):**
  - hazard tiers as a PNG overlay reprojected to EPSG:3857, with a legend;
  - no-observation hatched;
  - an optional `p_flood` layer labelled "model score (calibrated on global floods)";
  - pre/post VV dB greyscale;
  - S2 (if any);
  - exposed buildings and roads;
  - roads closed under the selected scenario (red);
  - settlements coloured by status, with a popup showing name, status, t0→t1 and trail access;
  - the flow path (if any).
- **Panel:**
  - inputs (scene ids, track, post lag, S2 used, OSM date);
  - **warnings** box;
  - hazard area table;
  - exposure table;
  - scenario counts + cut-off list;
  - downloads (sitrep PDF, hazard GPKG, settlements GPKG, GeoTIFF);
  - an **Evaluation** tab, shown only for runs listed in `docs/results/frozen_runs.txt`, displaying E1/E2/E4/E6 tables.
- **Footer:** the attribution strings.

- [ ] States: a "No valid same-track pair" red card (message from the run), an orange "partial run" card, a spinner per stage.
- [ ] The dashboard **never computes numbers**: it reads `results.json` and layers only.
- [ ] Smoke test: the app loads the mock run without exceptions; the scenario toggle changes the counts shown.

### P4.4 CI, README, fresh-clone (T+6 → T+12, then maintained)
- [ ] CI is already in `.github/workflows/ci.yml`; keep it green. Add the `network`/`gpu`/`slow` markers to any test that needs them.
- [ ] README sections:
  1. what it does;
  2. quickstart (conda env → `pip install -e .[app,pdf,ml]` → `.env` → `make mock` → `make app`);
  3. run the case study (cached + fast);
  4. reproduce training/eval (links to P2 docs);
  5. data rules + attribution;
  6. limitations;
  7. team + licence.
- [ ] Fresh-clone test at C2 and T+40: a teammate who didn't write the code follows the README on a clean machine. Record the result in `docs/plan/reports/fresh_clone.md`.

### P4.5 Integration checkpoints (C1 T+10, C2 T+24, FREEZE T+32)
At each checkpoint:
1. Merge the open green PRs in the order P1 → P2 → P3 → P4.
2. Run `cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --model <b0 | models/cutoff_unet_v1.pt>`.
3. `python -c "from cutoff.contracts_check import validate_run_dir; validate_run_dir('outputs/<id>')"`.
4. Open the dashboard.
5. Write `docs/plan/reports/C<n>.md` covering what works, what failed (owner + issue), timings, and screenshots.

- **C1 pass criteria:** a complete run folder in fast mode with b0; sitrep PDF; dashboard shows it.
- **C2 pass criteria:** the same with the trained model, plus one non-Trishuli AOI (from P1.8) in fast mode.
- **FREEZE:**
  1. Confirm `configs/default.yaml`, the checkpoint (sha256 in the report) and the code are final.
  2. `git tag frozen-v1 && git push --tags`.
  3. Produce the frozen evaluation runs (`outputs/trishuli_north_frozen`, `trishuli_south_frozen`) and list them in `docs/results/frozen_runs.txt`.

### P4.6 E4: EMSR927 check-only evaluation (harness T+12 → T+24; run ONCE after FREEZE)
**File:** `eval/emsr927.py`, `tests/test_p4_emsr_harness.py` (synthetic polygons only)
- [ ] Port blueprint §18.15 and extend it:
  - choose the observed-event layer(s) from the schema recorded in P4.0;
  - rasterise onto the run grid;
  - evaluate only the intersection of our grid with the EMS AOI extent;
  - pred = classes {1, 3, 4} (also report {1, 2, 3, 4});
  - pixel P/R/F1/IoU over valid pixels; boundary F1 at 30 m; the share of the reference that fell in no-observation;
  - **object-level** recall: the share of EMS-affected building footprints (if the layer exists) that lie in our hazard;
  - a 5 × 5 km tile grid of agreement for the figure.
- [ ] Disagreement taxonomy, filled by a human after looking at the maps: cloud/timing (EMS image date vs our post pass), radar geometry (shadow/layover), DEM/gorge, definition mismatch (EMS optical debris vs SAR water), OSM. Count tiles per cause.
- [ ] Credit line "European Union, Copernicus Emergency Management Service data" on every E4 figure/table.
- [ ] The run happens only after `frozen-v1`: the script refuses to run if `git describe --tags --exact-match` ≠ `frozen-v1` **or** the checkout is dirty. Write `docs/results/E4.md` + `outputs/<run>/emsr927_eval.json`. **No retuning afterwards**, whatever the numbers.

### P4.7 E7: runtime (T+24 → T+30)
- [ ] Time `cutoff run` (fast mode, b0 and trained model) for 10 × 10, 20 × 20 and 40 × 40 km AOIs on the demo laptop: wall time per stage and peak RSS from `run.log`. Write `docs/results/E7.md` [TARGET: 20 × 20 km ≤ 10 min in fast mode].
- [ ] Rehearse on an **unprepared AOI** chosen by someone else on the team (simulating the judges). Record what happened, including a graceful "no same-track pair" if that's what occurred.

### P4.8 Report ≤ 6 pages (T+30 → T+42)
**Files:** `docs/report/report.md` → `docs/report/report.pdf` (pandoc, or the same HTML→PDF path)
Outline with page budget:
1. Problem, users, the 3 questions (0.3 p).
2. System overview figure (pipeline) and the data rules followed (0.5 p).
3. Methods (1.5 p):
   - same-track pairing;
   - preprocessing (fast vs full, E3c);
   - the U-Net (7 ch, Kuro Siwo official split, calibration);
   - the disturbance rule;
   - gating;
   - exposure;
   - the network and scenarios.
4. Results (2 p):
   - E1/E2 (held-out, slope strata);
   - E4 (Trishuli vs EMSR927 + taxonomy);
   - E6 (scenario range + dropout);
   - E7 (runtime);
   - E3/E5/E8 if available.
5. **Limitations** (0.7 p): expanded from P4.1, plus what failed in E4.
6. Attribution + citations (0.5 p).

- [ ] Every number cites its results file. Targets are never presented as results.
- [ ] No victim imagery. "Educational prototype" appears in the abstract.

### P4.9 Video ≤ 3:00 + submission (T+38 → T+46)
Script (blueprint §19.5):

| Time | Content |
|---|---|
| 0:00–0:20 | the rescuer's question; disclaimer |
| 0:20–1:15 | Trishuli AOI + event → same-track pair → hazard tiers, no-observation, click for the reason |
| 1:15–1:50 | evaluation tab: E1/E2 + EMSR927 comparison and taxonomy |
| 1:50–2:30 | exposure + cut-off; toggle A/B/C; explain "unknown" and trail access |
| 2:30–2:50 | live run on a different valley |
| 2:50–3:00 | sitrep PDF, limitations, attributions |

- [ ] Submission checklist (`00_MASTER_PLAN.md` §7) completed and ticked in `docs/plan/reports/submission.md`.

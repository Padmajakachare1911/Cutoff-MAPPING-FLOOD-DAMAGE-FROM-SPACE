# V1/P4 submission integration

14 October 2026. User explicitly requested merging completed P2/v1 and P4 work into main, retaining v1 as the default and excluding the model-v2 experiment. Work was prepared in an isolated branch from remote main; the original experiment branch and user attachments were preserved.

## Included

- `p2/P2.8-permanent-water-terrain`: existing terrain/clear-S2 permanent-water gates, documentation and tests. Existing numerical thresholds, raster classes, grid and schema are unchanged.
- `p2/P2.11-evidence-gaps`: v1 slope-stratified calibration, H1 validation evidence and historical experiment log.
- `p2/P2.12-real-data-check`: v1 real-data check, derived figures/metrics and handoff.
- `p2/model-improvement-plan`: parked historical research and validation-only analysis; no new training or selection.
- P4 report/checklist feature history through `p4/P4.9-submission-checklist`, including the six-page report/PDF and source evidence snapshots.
- Consistent production defaults: configured v1 for CLI, direct pipeline, direct model stage and cache helper. Dashboard already selects the v1 checkpoint; the regression test now verifies that. Missing v1 is an explicit error; B0 remains a deliberately requested baseline.
- README/Makefile include ML installation for production v1. The README training example uses the supported named variant instead of an unsupported `--seed` flag.
- Updated handoffs and master-plan status link. Corrected stale cache-upload notes and partial-coverage alternate-track documentation.
- Latest team main OSM update included, with a safety repair: only exact-date/AOI/routing-buffer/filter caches can be reused; UTC offsets/subseconds preserved; no fallback to other dates. Stable ohsome v2 endpoint adopted. Four failing regression cases now pass; matching-cache reuse remains supported.
- Portable Markdown report images; HTML remains self-contained with embedded figures. Historical real-scene figures/runtimes are labelled as preceding this integration.

## Explicitly excluded

No merge/cherry-pick from `p2/model-v2` or `p2/model-v2-plan`. No v2 checkpoint, partial-label loss, mixed-source sampler/EMA, source builders, model-v2 training configuration or experiment dataset is added. The original released v1 asset remains git-ignored and unchanged:

`a2701cfcfbaa1d6facba585cb835aeff95607dadf6d6647ce84cb1d7fe380d46`.

## Verification

- Five behavioral default-selection tests were observed failing before implementation: CLI/pipeline configured v1, missing-v1 guard, direct model stage and cache helper. Focused suite after repair: **24 passed in 42.25 seconds**.
- Combined offline suite after the v1/P4 integration and default repair: **175 passed, 1 skipped, 4 deselected in 118.99 seconds**. Command: `PYTHONPATH=src`, `OMP_NUM_THREADS=2`, CUDA disabled, `python -m pytest -m "not network and not gpu" -o addopts="" -q -p no:warnings --basetemp C:/cutoff_data/v1_submission_full_tests --junitxml C:/cutoff_data/v1_submission_full_tests.xml`. Log: `C:/cutoff_data/v1_submission_full_tests.log`.
- The subsequent Markdown-image portability regression failed on absolute checkout paths, then passed after the builder repair. Both submission tests passed; HTML embedded PNGs and Markdown local assets are validated. Final CI checks cover the publication head.
- Final offline suite after the latest team OSM update and safety repair: **183 passed, 1 skipped, 4 deselected in 132.88 seconds**. Log/XML: `C:/cutoff_data/v1_submission_final_tests.log` and `C:/cutoff_data/v1_submission_final_tests.xml`. Focused OSM suite: **13 passed**.
- Actual released-v1 default selection exercised through the production model, disturbance, integrated gates, vectorize, settlements, exposure, access and PDF using only synthetic acquisition fixtures. Model checksum unchanged; contracts pass; exposure populated; all three scenarios; no partial warning; one-page sitrep. Evidence: `C:/cutoff_data/v1_submission_smoke/result.json`. This is not a complete real-data run or a new accuracy measurement.
- Six-page submission report rebuilt; all six pages visually inspected. Report still explicitly states actual E4/E6 and cold-runtime evidence pending.
- Existing live audit: this laptop's Sentinel Hub OAuth authenticated; ohsome v1 extraction returned 403; local `OHSOME_API_KEY` absent. Source cache-date defect was reproduced using synthetic vectors only.
- No new training, paid scene download, case-based tuning or EMSR927 prediction comparison was performed. No project-level freeze tag was created.

## Remaining work

See [TEAM_REMAINING_WORK.md](TEAM_REMAINING_WORK.md) for each P1-P4 task against the master plan and the exact credential prerequisites. Merged product code and green unit tests do not complete the real-data acceptance or competition submission. The critical blockers remain actual dated OSM coverage/access, complete real integration, intentional freeze and final E4/E6/rehearsal/submission evidence.

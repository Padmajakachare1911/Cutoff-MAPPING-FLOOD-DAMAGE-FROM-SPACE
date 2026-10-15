# Project audit and repairs — 15 October 2026

## Verdict against the master plan

Cutoff implements the intended flood **evidence, exposure and road-access** product:
same-track Sentinel-1 → linear backscatter on a 10 m UTM grid → Copernicus
terrain/optional Sentinel-2 → released v1 U-Net plus scene-adaptive change →
hazard tiers → dated pre-event OSM → settlements and A/B/C routing → validated
Results → local MapLibre dashboard and one-page situation report.

The MapLibre implementation is the explicitly accepted 14 October update to the
master plan. The final model keeps the seven-channel interface and suppresses
the slope channel as documented by P2. This audit does not change weights,
calibration, thresholds, training splits or input-data rules.

The project is broadly aligned with the plan, but its **submission definition of
done remains incomplete**. Green implementation tests do not establish local
flood accuracy or competition readiness.

Reviewed sources include the master plan, stream/interface plans, stage and
product source, tests, evaluation/report tooling, handoff/evidence records, and
the downloaded `C:/Users/524ta/Downloads/Cutoff_Solution.md`. Original PDFs and
historical outputs remain supporting material; they are not new measurements.

## Verified bugs repaired

| Issue | Repair | Evidence |
|---|---|---|
| Densification joined roads at different levels when generated vertices happened to share coordinates. A bridge/underpass example incorrectly had one connected component. | Graph endpoints now merge only within the same original way, compatible grade, or shared original way endpoints. Settlement snapping retains the resulting node identity. | Regressions fail before repair for bridge, tunnel and differing-layer crossings; legitimate bridge approaches and parallel edges remain connected appropriately. |
| Scenario A closed bridges on class 2/3 approach evidence, contrary to master-plan D8. | Every scenario requires high-confidence class 1/4 evidence at bridge approaches. Non-bridge scenario rules and numeric thresholds are unchanged. | Parameterized A/B/C approach regression; P3 stream brief clarified to match D8. |
| Failed SNAP processing left a final cache filename that a retry reused; even exit-zero invalid output was published. | GPT writes a temporary GeoTIFF, reads it successfully before atomic publication, and cleans temporary output on failure. Invalid existing raster caches trigger regeneration. | Failed-process/retry and invalid-output regressions fail before repair and pass afterward. |
| E6 counted closed bridge segment IDs, overcounting long bridge ways after densification. | E6 reads the original bridge-way count from validated Results, matching the access stage and dashboard. | Two segments belonging to one bridge report one closed bridge. |
| Results omitted the plan's assumption for routes outside observed hazard coverage. | New Results include the limitation that roads outside the analysis AOI are assumed open. | Pipeline/integration checks and real-run Results. |
| Written report still named Streamlit and claimed OSM/access integration was blocked. | Builder and generated Markdown/HTML/PDF now describe the selected local dashboard and documented complete integration. Historical partial runtimes remain explicitly historical. | Rebuilt PDF is six pages; submission tests pass; all pages inspected. |

## Local SNAP and model

- Downloaded installer: `esa-snap_sentinel_windows-14.0.0.exe`.
- SNAP is already installed at `C:/Program Files/esa-snap`; version file is **14.0.0**.
- `find_gpt()` resolves `C:/Program Files/esa-snap/bin/gpt.exe` automatically.
- `python -m cutoff.data.snap --check-gpt`: **ok**, all seven graph operators
  recognize every requested parameter. No reinstall is needed.
- CDSE username/password are configured locally. Presence is not a fresh
  authentication or cold product-download test.
- Local model-v1 SHA-256 matches the documented release:
  `a2701cfcfbaa1d6facba585cb835aeff95607dadf6d6647ce84cb1d7fe380d46`.

## Verification

- Final consolidated offline suite: **210 passed, 4 deselected**, in 127.64 s;
  `outputs/audit/final-tests.xml`. Rebuilt report checks also pass (two tests).
- Critical Python lint (`E9,F63,F7,F82`) and `git diff --check` pass. The broader
  inherited Ruff style configuration reports existing style issues; no global
  formatting rewrite was performed.
- Trishuli cached v1 pipeline: `outputs/audit/audit_trishuli_verified_20261015`,
  complete, no warnings, hazard **0.249 km²**, scenario A/B/C cut-off counts
  **28 / 0 / 0**. A separate final-code access recheck under
  `outputs/audit/trishuli_access_recheck` passes all six access layer contracts,
  with the same counts and one closed bridge per scenario.
- Deir cached v1 pipeline: `outputs/audit/audit_deir_verified_20261015`, complete,
  hazard **10.479 km²**, scenario A/B/C cut-off counts **75 / 0 / 0**. The expected
  lowland HAND fallback warning remains. Its scenario-A count differs from the
  previously recorded 77 following the grade/bridge correctness repairs; this is
  an algorithm correction, not a measured accuracy improvement.
- Both complete run folders pass the full contract validator, have one-page
  sitreps, and load as complete in the actual dashboard server's Results adapter.
  Compact local evidence: `outputs/audit/verification.json`.
- These runs use prepared satellite and exact dated OSM caches. They are not
  cold acquisition, independently chosen AOIs, or a fresh-clone rehearsal.
- On this restricted machine, Numba cache initialization tried writing into the
  installed Python package directory and stalled. The full suite and real
  terrain checks required the approved execution outside that filesystem
  restriction. Project outputs remain under `outputs/audit/`.

## Outstanding plan requirements

1. Independent fresh-clone and unprepared-AOI rehearsal, including live inputs.
2. Resolve organiser questions about fast/cached processing, published training
   preprocessing, pretrained encoders and language requirements.
3. Intentional final code/config/v1 review and clean `frozen-v1` tag. No such tag
   currently exists; this bug-fix pass does not create a project freeze.
4. Run the once-only check-only E4 evaluation after that freeze, then produce
   real frozen E6 dropout/transport evidence and the prescribed cold E7 sweep.
5. Refresh final evidence tables and submission assets, resolve the previously
   deferred video requirement, and submit.

The source leak guard passes. No reference evaluation, new model selection,
threshold tuning, organiser message or final submission was performed here.

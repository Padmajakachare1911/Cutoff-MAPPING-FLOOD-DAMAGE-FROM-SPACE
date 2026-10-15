# Main integration — 15 October 2026

The working checkout was already on `main`, aligned with `origin/main` at
`d5706f5`. GitHub had no open pull requests. This integration records the pending
project changes on that branch; it does not combine historical experiment branches
or change the production model selection.

## Included work

- Wide responsive dashboard workspace, navbar run selection and external map information.
- Dated Sentinel-2 comparison, separate flood/change/score layers, original radar,
  optical water, no-observation hatching and labelled historical display context.
- Measured 3D terrain, contours, true-scale defaults, footprint-only buildings,
  overlay registration/source popups and preserved saved results.
- Representative settlement anchors inside real member buildings, grade-aware
  graph endpoints, corrected bridge-approach closures and bridge-way evaluation counts.
- Atomic publication/validation of SNAP raster caches and disclosure of the
  assumption that roads beyond observed hazard coverage remain open.
- Updated written report, attribution, supporting research originals and audit records.
- Detailed project README covering outcomes, architecture, layer meanings,
  models/benchmarks, reviewed cases, setup, commands, artifacts and limitations.
- Conda `pyarrow>=14` aligned with the corrected package requirement; optional
  SNAP/data-root settings added to the environment template.

`video/` remains local and is excluded through the root `.gitignore`. Model weights,
private credentials, prepared caches and generated run archives remain excluded.

## Verification

- `python -m pytest -m "not network and not gpu"`: **223 passed, 4 deselected**
  in 161.41 seconds. The 84 warnings are inherited rasterio/Affine deprecations.
- Critical Python lint (`E9,F63,F7,F82`), modified JavaScript syntax checks and
  whitespace checks pass.
- README local document links resolve, and the `model-v1` GitHub release contains
  `cutoff_unet_v1.pt` (97,969,582 bytes).
- The README's synthetic CLI command creates a new demo and report. On this
  Windows installation it uses the documented xhtml2pdf native-library fallback.
- That new demo passes the complete run contracts and produces a one-page PDF.
  A freshly initialized dashboard passes 14 HTTP checks covering the workspace,
  configuration/history, both map viewers, A/B/C map data, flood/change/score/
  no-observation PNG layers and the PDF download.

These are implementation/reproducibility checks. This integration does not create
the `frozen-v1` project tag, run the once-only external evaluation, claim a cold
satellite acquisition, or complete the remaining submission acceptance gates.

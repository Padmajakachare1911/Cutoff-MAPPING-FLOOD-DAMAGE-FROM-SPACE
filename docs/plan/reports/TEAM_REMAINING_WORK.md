# P1-P4 remaining-work audit against the master plan

Checked 14 October 2026 against `00_MASTER_PLAN.md` sections 1, 4 and 7, the four stream plans, task reports, Git history, live credential checks and local tests. Template `[ ]` boxes in the original stream briefs are requirements, not a reliable status board. This audit separates implementation from actual acceptance evidence.

**Production choice: released model-v1.** Completed v1 gating/evidence and P4 report/checklist history are included in this integration. Model-v2 branch history, builders, training changes and weights are excluded. No new training or model/temperature/threshold selection occurred. B0 remains an explicitly requested baseline; synthetic development data stay labelled mock.

## Remaining work by person

| Owner | Remaining build/fix work | Remaining data, measurement or submission work |
|---|---|---|
| **P1** | No unfinished core acquisition/terrain/S2/SNAP implementation was identified. Keep documented backend and DEM limitations. | Ensure every teammate can use the uploaded cache, especially Trishuli south; verify live inputs on the submission machine and supply the real/cold acquisitions required by P4. The uploaded Drive link is recorded in P1.8; the older checklist's upload-pending entry was stale. |
| **P2** | No required new model training. V1 defaults and pending gating/evidence/report work are integrated. | Confirm released v1 SHA and model statistics/thresholds in the final product; carry real-scene/calibration limitations into the final report. The project-wide freeze is a later P4/team step. Missing optional isolated-difference/flip ablations are not invented or run on submission day. |
| **P3** | **Fix direct-stage OSM cache provenance/identity**: snapshot, access extent/settings and source date must bind cached data. P4's namespace mitigation does not repair the direct API. Review the current stable v2 endpoint. | Obtain ohsome v2 access or verified dated caches for roads/places/health over the full 15 km routing buffer and buildings in each AOI. Complete real settlements/exposure/A-B-C routing, live bonus flow-path acceptance, real E6 scenario/dropout measurements and post-freeze transport comparison when applicable. |
| **P4** | Core product/evaluation/runtime/report tooling is implemented. No missing basic dashboard/PDF implementation was identified. | Complete real north/south plus non-Trishuli runs; validate full exposure/access and dashboard/PDF; conduct independent fresh-clone and unprepared-AOI rehearsal; intentionally freeze reviewed clean code/config/v1; run E4 once; collect real E6 and prescribed cold-size E7; refresh the six-page report/checklist. Resolve organiser questions, record the deferred <=3-minute video if required, and perform final submission. |

The immediate critical path is **OSM access + provenance -> complete real integration -> intentional freeze -> E4/E6 -> final report/rehearsal/submission**. More model training does not resolve those blockers.

## P1 task mapping

| Plan task | Verified status | Evidence / qualification |
|---|---|---|
| P1.0 setup/recon | Implemented, historical live evidence recorded | P1.0/P1.1 and STAC fixtures; local Sentinel Hub OAuth also succeeded during the integration audit. |
| P1.1 pair selection | Implemented/tested | Exact date/orbit/coverage contracts and P1.1 report. The master-plan alternate-track statement was corrected: 121D is insufficient coverage on these AOIs; 19D is the full-coverage alternate. |
| P1.2 speckle | Implemented/tested | Lee Sigma tests and real runs. |
| P1.3 Sentinel Hub | Implemented/tested, live authentication available locally | This audit's token request succeeded; no claim that a fresh paid scene request was run in this audit. |
| P1.4 S1 stage/cache | Implemented/tested | Real north/south/Deir runs documented; clipping of real linear sigma0 above the current validator range remains disclosed. |
| P1.5 terrain | Implemented/tested | GLO-30/HAND/slope/D8 evidence; DEM smoothing and D8 behavior are documented limitations. |
| P1.6 S2 | Implemented/tested | After-event S2 selection is a documented deviation from the literal +/-5 day window. Do not silently revert it. |
| P1.7 SNAP | Implemented; historical SNAP-14/full-chain acceptance recorded | Not rerun on this laptop in this merge task. CDSE login and local SNAP are required for full mode. |
| P1.8 cache/E3c/E5 | Cache upload and experiments recorded | P1.8 contains the Drive link. E3c's <=0.5 dB target is narrowly missed at pixel scale, and hazard-rule differences are reported; a missed target is a result, not an unfinished implementation to conceal. |

## P2 task mapping

| Plan task | Verified status | Evidence / qualification |
|---|---|---|
| P2.0-P2.1 setup/subset | Implemented; original frozen data preserved | 27 train events/9,114 patches, six validation events/1,145 and ten test events/4,250. |
| P2.2 SAR input | Implemented/tested | NaN-safe dB, linear pre-mean and slope construction. |
| P2.3 dataset/QA | Implemented/tested; QA evidence recorded | Kuro schemas/normalization/ignore rules. |
| P2.4 training/calibration | Completed for v1 | Released no-slope seed-42 checkpoint, original training log and calibration. No retraining for this integration. |
| P2.5 B0/inference | Implemented/tested | V1 is the production default from the existing config; explicit B0 and custom checkpoint overrides still work. |
| P2.6 B1 | Completed optional reference | Released SNUNet comparison; fairness limitations remain in results. |
| P2.7 disturbance | Implemented/tested | Existing robust scene-level change rule and lowland fallback unchanged. |
| P2.8 gating | Completed, including pending v1 fixes | Permanent-water terrain/clear-S2 checks and regression tests integrated; no new numerical thresholds. |
| P2.9 vectorize | Implemented/tested | Contract-valid UTM polygons/areas. |
| P2.10 model selection/release | V1 chosen and released | Weights/T/tau unchanged. This is distinct from the still-pending clean project `frozen-v1` tag. |
| P2.11 E1/E2/E3/E8 | Measured evidence integrated | Pooled/per-event/slope, post-only/slope/data-size ablations, seed check and slope-stratified calibration. Separate difference-only or flip comparisons are not claimed where no experiment exists. |
| P2 real-data handoff | Integrated | P2.12 reports weak desert/gorge transfer honestly and the measured display-gating fixes. |

## P3 task mapping

| Plan task | Verified status | Evidence / qualification |
|---|---|---|
| P3.0 OSM recon | Historical v2 north-AOI recon complete | Four small dated fixtures and recorded counts/columns. This is not full 15 km buffer coverage or a key configured on this laptop. |
| P3.1 OSM stage | Implemented/tested; integrity repair still required | Open issue #25 reproduced with synthetic July cache reused as May through direct stage. CLI/pipeline snapshot namespace mitigates its route. |
| P3.2 settlements/targets | Implemented/tested | Real complete-run acceptance awaits the required buffered OSM. |
| P3.3 exposure | Implemented/tested | Actual algorithm integration passes synthetic acquisition; real asset exposure remains unmeasured in the partial runs. |
| P3.4 access | Implemented/tested | Noding, grade/bridge/parallel-edge handling, scenarios and four statuses tested. Real routing completeness not established. |
| P3.5 bonus flowpath | Implemented/tested on synthetic data | Live Lhende/Bhote Koshi/Trishuli path and named-place acceptance map remain pending; current cached-mode flowpath is skipped. |
| P3.6 E6 | Tooling implemented; real evidence pending | Frozen scenario/Jaccard/20-run dropout table and post-freeze external transport check required by the plan. |

## P4 task mapping

| Plan task | Verified status | Evidence / qualification |
|---|---|---|
| P4.0 analysis/reference schema | Implemented; schema inventory recorded | No reference prediction comparison before freeze. |
| P4.1 pipeline/CLI | Implemented/tested | V1 selection defaults now consistent; timestamp guards, stage dependencies, optional/partial failures and fresh run folders tested. |
| P4.2 one-page sitrep | Implemented/tested | Strict escaped template, attribution and Windows PDF fallback. |
| P4.3 dashboard | Implemented/tested | V1 checkpoint selected by default; scenario toggle, error state and map overlays tested. |
| P4.4 CI/install/README | Implemented; isolated wheel evidence recorded | Independent teammate fresh-clone case-study rehearsal still pending. |
| P4.5 full C1/C2/freeze | Synthetic integration passes; real acceptance incomplete | Existing real hazard/PDF runs explicitly have unavailable OSM/access. No clean project freeze is created by this merge task. |
| P4.6 E4 | Guarded harness implemented/tested | Actual once-only comparison, tile figure and human disagreement taxonomy await final integration/freeze. |
| P4.7 E7 | Collector implemented; partial/warm-cache timings recorded | Cold 10/20/40 km B0/checkpoint sweep and <=10-minute 20 km target remain unverified. |
| P4.8 six-page report | Report/PDF/builder integrated | Must be refreshed after actual E4/E6/cold-runtime results; existing figures/timings are explicitly historical, before these gates/default changes. |
| P4.9 checklist/video/submission | Checklist integrated | Video was explicitly deferred in P4's handoff. Whether the final submission requires it must be resolved; no video or final competition submission is claimed. |

## Keys and private configuration required

| Purpose | Configuration | Current local status |
|---|---|---|
| **Historic OSM extraction** | **`OHSOME_API_KEY`** from [HeiGIT account](https://account.heigit.org/signup) | **Missing; immediate blocker.** Use the key for historical extraction, not an OSM website login or generic map-tile token. |
| Fast Sentinel-1/2 | `SH_CLIENT_ID`, `SH_CLIENT_SECRET` | Present; local OAuth authenticated. Each submission machine needs working values. |
| SNAP/full download | `CDSE_USERNAME`, `CDSE_PASSWORD`; local `SNAP_GPT` executable | Needed only for full mode; check on the machine actually used. S3 credentials are an alternative download route, not required when OData works. |
| Hugging Face download | `HF_TOKEN` if the selected download needs it | No new Kuro download/training is needed to use the existing v1 release. |

HeiGIT's 8 October release notice specifies the stable base `https://api.heigit.org/ohsome-api/v2/`; `/v2-rc` is deprecated. The current repo's OSM config still names the old base, so P3 should update/verify it with a real key. Source: [official release notice](https://heigit.org/ohsome-2-0-has-arrived-2/), [API access and free standard key](https://api.heigit.org/), [historical extraction API](https://docs.ohsome.org/ohsome-api/v2/reference/api.html).

Add `OHSOME_API_KEY=...` directly to the ignored local `.env` or the process environment. Do not put the actual key in Git, issues or this document. If using caches instead, require verified acquisition provenance, the exact pre-event snapshot and full buffered routing coverage. Trishuli uses 2026-07-27; Deir's May event needs an earlier snapshot such as 2026-05-01. A key alone does not repair cache identity or prove routing coverage.

## Evidence and verification boundaries

The previous main audit recorded 164 executed offline cases passing across the full run and map-dependency retry, actual released-v1 synthetic-input integration with all three scenarios and one-page PDF, successful local Sentinel Hub OAuth, ohsome v1 geometry HTTP 403, missing v2 key and a synthetic reproduction of issue #25. Evidence remains at `C:/cutoff_data/integration_audit`.

For this integration, five behavioral default-selection tests were observed failing before the repair. The focused pipeline/inference/dashboard suite passed **24 tests in 42.25 seconds** afterward. The final combined-suite and publication verification is recorded in `V1_MAIN_INTEGRATION.md`. No test-only reference evaluation, paid live scene acquisition, new model training or new real-scene selection occurred in this merge task.

The master plan's final definition of done is not fully met until complete real runs, real E4/E6 evidence, the intentional freeze, independent rehearsal and final submission assets are verified. Do not replace those unchecked gates with green unit-test or merge status.

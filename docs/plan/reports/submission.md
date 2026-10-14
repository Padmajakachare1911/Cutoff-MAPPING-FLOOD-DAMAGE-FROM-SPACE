# Submission checklist - checked 14 October 2026

P4's independent implementation is delivered. The OSM integrity repair is now
included in the v1 submission integration; P4's recorded video deferral remains. This
checklist separates delivered product work from competition evidence still needed;
it does not certify the entire project ready for submission.

## P4 delivered

- [x] Whole-codebase architecture/contracts/P1-P3 handoffs analysed; P4 workflow documented.
- [x] Separate p4/P4.0 through P4.9 feature branches and task PRs created.
- [x] Pipeline/CLI, timestamp validation, stage contracts, logs/timings/RSS implemented.
- [x] Core errors, optional S2 and partial OSM/access states tested.
- [x] Snapshot-isolated P4 cache safeguard; underlying P3 fix notified in #25.
- [x] One-page A4 sitrep, strict/escaped template, PDF fallback and attribution tests.
- [x] Dashboard map layers, no-observation, exposure/access tables, A/B/C, warnings/downloads.
- [x] Actual P2/P3 algorithm integration against synthetic acquisition passes contracts and PDF.
- [x] Real satellite/terrain/hazard runs completed for Trishuli and Deir; partial OSM state explicit.
- [x] Final model release checksum and loading verified; no threshold/model retuning.
- [x] EMSR927 delivered package schema/date/legend inventory prepared without prediction comparison.
- [x] Isolated E4 harness, valid/extent/boundary/object/tile metrics, clean-tag/once-only guards tested.
- [x] E7 collector and reproducible 10/20/40 km B0/checkpoint benchmark implemented.
- [x] Actual warm-cache/partial runtime table recorded with source JSON and machine metadata.
- [x] README/direct Windows quickstart; packaged resources; clean wheel installation verified.
- [x] Separate Linux/Windows pipeline/report/dashboard/evaluation/runtime CI workflows.
- [x] Six-page report generated, page-count tested and every page visually inspected.
- [x] No victim imagery; disclaimer and required credits present; reference-leak guard retained.
- [x] Final offline suite: **165 passed, 1 skipped, 4 deselected**; P4 lint passed.
- [x] Tracked-file credential scan passed; supplied credentials remain outside Git.

## Team / data / final submission gates still open

- [x] Underlying OSM cache identity fixed in the integration: exact UTC date/AOI/buffer/filters; other-date fallback removed (#25). Real dated buffered OSM acquisition is now verified in the live integration report.
- [x] Ohsome v2 authenticated and real dated **15 km buffered** OSM acquired for north/south/Deir; #31 repair and evidence in [P4_LIVE_INTEGRATION.md](P4_LIVE_INTEGRATION.md).
- [x] This laptop's Sentinel Hub OAuth client/secret authenticated during the 14 October integration audit. Other teammates still need their own working credentials.
- [x] Complete real north/south/Deir exposure, A/B/C access, contracts, one-page PDF and dashboard verified. Satellite caches are warm; south's final rerun uses its newly acquired matching OSM cache.
- [ ] Independent teammate fresh-clone test and an independently chosen unprepared AOI rehearsed.
- [ ] Organiser questions answered (cached/fast acceptance, Kuro preprocessing, Nepali PDF, encoder weights).
- [ ] Final code/config/checkpoint reviewed; clean `frozen-v1` tag created **before** real E4.
- [ ] E4 run once, real table/tile figure and human disagreement taxonomy completed; no retuning afterwards.
- [ ] Real E6 scenario range/dropout table added after corrected-data integration.
- [ ] Cold 10/20/40 km fast-mode B0/checkpoint E7 sweep measured; [TARGET] <=10 min at 20 km checked.
- [ ] Report refreshed with the above actual E4/E6/cold-runtime evidence before competition submission.
- [ ] Demo video <=3:00: **deferred explicitly by the user; no video created**.
- [ ] Final competition submission performed by the team.

## Exact next commands after reviewed integration

```text
cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --model models/cutoff_unet_v1.pt --run-id trishuli_north_frozen
python -c "from cutoff.contracts_check import validate_run_dir; validate_run_dir('outputs/trishuli_north_frozen')"
python eval/access_eval.py outputs/trishuli_north_frozen --out outputs/trishuli_north_frozen/access_eval.json
```

After all complete-run evidence passes and the team intentionally freezes a clean
checkout, run `eval/emsr927.py` once per frozen case; do not tune afterwards. Use
`python eval/runtime.py --benchmark` for the prescribed size sweep. Then rebuild
`python docs/report/build_report.py`, review the updated report, and record the
checks here. Do not turn unchecked gates into claimed results.

## V1 submission integration update

The original P2 v1 gates/evidence and P4 report/checklist history are included in
the submission integration. Configuration, CLI, direct pipeline/model stage and
cache helper consistently choose model-v1 unless explicitly overridden. No v2
experiment code or weights are included. See [TEAM_REMAINING_WORK.md](TEAM_REMAINING_WORK.md)
for the task-by-task master-plan audit; source implementation does not imply the
unchecked real-data acceptance gates above are complete.

## Live integration update

Issue #31 has been reproduced and repaired on `p4/live-integration-unblock`.
Private authentication passed; OSM request pacing/429 recovery and a highway-area
parsing failure were fixed. All three final runs completed. Final offline suite:
**188 passed, 1 skipped, 4 deselected**. See [P4_LIVE_INTEGRATION.md](P4_LIVE_INTEGRATION.md)
for provenance, the cached south rerun and remaining submission boundaries.

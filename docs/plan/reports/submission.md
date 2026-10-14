# Submission checklist - checked 14 October 2026

P4's independent implementation is delivered. The user assigns the underlying
data-integrity fix to the teammate and explicitly defers the demo video. This
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

- [ ] Underlying OSM cache provenance fixed by teammate (#25; user says evening).
- [ ] Ohsome v2 key or verified dated **15 km buffered** OSM caches available (#31).
- [ ] Supplied live Sentinel Hub client/secret authenticate; CDSE account login itself is verified.
- [ ] Complete real fast-mode Trishuli + non-Trishuli runs, exposure/access and fresh-clone case study verified.
- [ ] Independent teammate fresh-clone test and an independently chosen unprepared AOI rehearsed.
- [ ] Organiser questions answered (cached/fast acceptance, Kuro preprocessing, Nepali PDF, encoder weights).
- [ ] Final code/config/checkpoint reviewed; clean `frozen-v1` tag created **before** real E4.
- [ ] E4 run once, real table/tile figure and human disagreement taxonomy completed; no retuning afterwards.
- [ ] Real E6 scenario range/dropout table added after corrected-data integration.
- [ ] Cold 10/20/40 km fast-mode B0/checkpoint E7 sweep measured; [TARGET] <=10 min at 20 km checked.
- [ ] Report refreshed with the above actual E4/E6/cold-runtime evidence before competition submission.
- [ ] Demo video <=3:00: **deferred explicitly by the user; no video created**.
- [ ] Final competition submission performed by the team.

## Exact next commands after data is ready

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

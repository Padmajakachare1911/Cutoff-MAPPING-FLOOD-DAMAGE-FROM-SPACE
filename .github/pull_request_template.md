## What
<!-- task id(s) from docs/plan, e.g. P1.2 -->

## Checklist (all must be true before merge)
- [ ] Only files owned by my stream changed (docs/plan/00_MASTER_PLAN.md §4), or a `contract-change` label + 4 approvals
- [ ] `pytest -m "not network and not gpu"` green locally and in CI
- [ ] Stage output passes `validate_run_dir(...)` on the mock run AND on a real run (if a stage)
- [ ] No EMS / UNOSAT / post-event OSM used as an input; nothing under `src/` reads `reference/`
- [ ] No unmeasured number written as a result (targets are labelled [TARGET])
- [ ] Task report updated: `docs/plan/reports/<task>.md` (what was done, test output, open issues)

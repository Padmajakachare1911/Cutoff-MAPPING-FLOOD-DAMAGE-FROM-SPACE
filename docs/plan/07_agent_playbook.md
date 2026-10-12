# Agent playbook — how each person drives their AI coding agents

All four people build with AI agents. These rules keep four agents from colliding, drifting from the contracts, or claiming work they didn't verify.

## 1. One agent session = one task
Give the agent exactly one task id (e.g. `P1.3`). Paste the brief below and point it at files instead of pasting history. When the task's acceptance tests pass and the PR is open, end the session and start a fresh one for the next task.

## 2. Task brief template (copy, fill, paste)

```
You are implementing task <ID> of the Cutoff project (Multimodal AI Hackathon 2026, Track B).
Repo: <path>. Branch: p<N>/<ID>-<slug> (create it from origin/main).

Read first, in this order:
  1. docs/plan/00_MASTER_PLAN.md   (sections 1, 2, 4)
  2. docs/plan/05_contracts.md     (the interfaces you must honour)
  3. docs/plan/0<N>_*.md           (your stream) - task <ID> is your requirements; use its exact values
  4. src/cutoff/contracts.py, src/cutoff/runctx.py, the stub you are replacing

Rules:
  - Edit ONLY files owned by stream P<N> (00_MASTER_PLAN.md section 2). Need a change elsewhere? Stop and tell me.
  - Never edit contracts.py / runctx.py / grid.py / schema.py / contracts_check.py.
  - TDD: write the task's tests first, run them and see them fail, implement, run them and see them pass.
  - Stage outputs must pass cutoff.contracts_check.validate_run_dir on the mock run (python -m cutoff.mock outputs/demo_mock).
  - Never use Copernicus EMS, UNOSAT, GEOID-Flood, MMFlood, ImpactMesh, JRC, WorldCover, GHSL or post-event OSM as inputs.
  - Tests needing internet/credentials get @pytest.mark.network; GPU ones @pytest.mark.gpu.
  - Don't claim a number you didn't measure. Targets are written as [TARGET].

When done:
  - Run: pytest -m "not network and not gpu"  (must be green), plus your network tests if you have credentials.
  - Write docs/plan/reports/<ID>.md: what was built, the exact test commands + output tail, open issues, deviations.
  - Commit with a conventional message, push the branch, open a PR using the template.
  - Reply with: status (DONE / DONE_WITH_CONCERNS / BLOCKED), PR link, a one-line test summary, concerns.
```

## 3. Review before merge (the human does this, ~5 min per PR)
1. CI is green.
2. The diff touches only owned files.
3. The tests assert behaviour (not just "runs").
4. The report contains the real test output.
5. For stages: `validate_run_dir` is called in a test.
6. No hard-coded Trishuli values outside tests/configs.
7. Nothing is read from `reference/`.

If something fails, send the agent the specific finding; don't fix it yourself mid-session.

## 4. Parallel safety
- Four people × one agent each, working on different files, is safe. Two agents in the same stream is safe only if their tasks touch disjoint files (e.g. P1.2 speckle and P1.5 terrain).
- Always `git fetch && git rebase origin/main` before pushing; resolve conflicts in your own files only.
- A merged contract change → every stream rebases within 1 h and re-runs its tests.

## 5. Status board
Keep a pinned issue "Status board" with one line per task: `P2.4 | in progress | ETA T+18 | blocker: none`. Update it on every PR. P4 reads it before each checkpoint.

## 6. When an agent is stuck
- **BLOCKED on missing info** (credentials, an external API change): post on the status board and move to your next independent task.
- Two failed attempts at the same fix → stop, re-read the verification log (`06`), and check the external API docs again. APIs changed in 2026 (ohsome v2, Sentinel-1C/D).
- A blocker on the critical path (P2.1/P2.4) is escalated to the whole team at once; use the fallback ladder in `00_MASTER_PLAN.md` §3.

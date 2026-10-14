# P4 implementation workflow

Starting point: main `c695f73260ca106e616453031a4e697f17ea2c0e`, 14 October 2026.
P1/P2/P3 merged; P4 orchestrator, CLI, report, dashboard and evaluation are absent.

Each task gets its own `p4/P4.<n>-<feature>` branch and PR. Dependencies are
explicit; merge only after local acceptance tests and GitHub CI pass. Workflows
below describe execution and evidence, not a claim that external checks passed.

| Task / branch | Depends on | Work and acceptance |
|---|---|---|
| P4.0-analysis-setup | main | Audit all modules, baseline suite, fetch model/reference metadata, log questions |
| P4.1-pipeline-cli | P4.0 | Test fake-stage integration/errors first; orchestrate real stages, validate outputs, CLI, timestamp/cache guards |
| P4.2-situation-report | P4.1 | Strict template; HTML/PDF fallback; one-page, attribution, partial/long-list tests; visual QA |
| P4.3-dashboard | P4.2 | JSON-only statistics, projected raster overlays, scenario layers, run subprocess/progress, downloads, AppTest |
| P4.4-ci-quickstart | P4.3 | Feature CI, packaged resources, README/Makefile, isolated fresh install and demo |
| P4.5-integration | P4.4 | Real cached/fast case studies and model checksum; C1/C2 evidence; freeze only if prerequisites pass |
| P4.6-check-only-evaluation | P4.4 | Synthetic tests for clipped extent, valid pixels, boundary/object recall, 5 km tiles; clean frozen tag guard |
| P4.7-runtime | P4.5 | Reproducible size/model benchmark; measured log extraction; explicitly distinguish cached from fast |
| P4.8-submission-report | P4.6/P4.7 | Source-linked report <=6 pages; measured tables; unavailable evidence clearly labelled; visual QA |
| P4.9-demo-submission | P4.8 | <=180 s demonstration, script/captions, checklist and handoff; no invented real-world evidence |

## Integration safeguards

- Keep frozen contracts and P1/P2/P3 source intact. P4 wraps existing interfaces.
- Reject post-event OSM before any stage. Isolate OSM caches by timestamp and extent
  settings; never trust undated legacy OSM cache as pre-event evidence.
- S2 is optional; remove failed S2 outputs so they cannot enter gating.
- Stop dependent P3 stages after a soft failure and publish partial results.
- Core failure writes error.json without results.json. NoValidPair reaches CLI verbatim.
- Display model score and exposure honestly; permanent-water artefacts remain a limitation.
- Check-only products are confined to eval/ and ignored reference storage; never pipeline inputs.
- Freeze and E4 require real-data readiness; synthetic demo success does not satisfy that gate.

## External prerequisites

The user does not know credential locations or organiser answers. Attempt public P1
Drive cache retrieval and model-v1 release download. Organiser communication has no
known recipient/channel; prepare questions without inventing answers or sending to
an unrelated person. Any inaccessible data is recorded with the observed failure.

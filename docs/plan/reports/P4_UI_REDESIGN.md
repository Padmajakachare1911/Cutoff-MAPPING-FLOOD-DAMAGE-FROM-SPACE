# Dashboard redesign — 15 October 2026

The subsequent [map story rebuild](P4_MAP_STORY.md) supersedes the map presentation
described here, adds dated display imagery and historical Sentinel-2 context,
and documents the later browser/test checks. This file records the initial
dashboard layout pass.

The user requested a complete readability and layout overhaul of the local
dashboard, particularly its overflowing run archive and settlement panel.

## Delivered experience

- Light workspace with a restrained Cutoff red accent, high-contrast text,
  larger summary numbers, consistent card spacing and aligned sections.
- Separate **Run archive** and **New analysis** tabs. History has readable
  names/timestamps, status filtering, search and eight-run pagination. Full run
  IDs remain available without stretching the layout.
- A prominent situation map with a bounded access panel. Settlement lists have
  search, four-item pagination, cut-off/degraded filtering, correct direction
  for multilingual names and buttons that locate a settlement on the actual map.
- Clearly labelled A/B/C policies and status counts. Unknown access and inferred
  closures retain their uncertainty wording. Numbers still come from Results.
- Map layers and the legend use collapsible, readable controls. Terrain,
  satellite evidence, hazard, no observation, optional optical/flow evidence,
  assets and closure overlays retain their existing data paths.
- Grouped hazard/exposure tables and exports, a quick PDF download, and
  expandable provenance, limitations and frozen-run evaluation.
- Mobile controls open in a keyboard-accessible drawer; setup fields scroll
  independently while Run Analysis remains visible. Reduced-motion preferences
  are respected. System fonts replace the external font dependency.

Implementation: `app/static/{index.html,styles.css,controls.css,app.js,map.html,map.css,map.js}`.
The existing Python server, pipeline and data contracts are retained. No hosting
deployment, analysis launch or new input dataset was needed for this redesign.
The Sites skill was used with its local-checkout/preview workflow.

## Verification

- **35 tests passed** across contracts, dashboard APIs, map animation, pipeline
  and integration; the focused 11 dashboard checks also passed after the final
  layout changes. JavaScript syntax checks and `git diff --check` pass.
- Actual browser verification against the existing local server and real Deir
  Results: A/B/C counts match, archive and settlement search/pagination work,
  degraded filtering and settlement-to-map navigation work, available layers
  toggle, the PDF downloads, and provenance/limitations expand correctly.
- Failed historical runs clear completed-run figures/downloads. Partial/running
  payload fixtures separately verify unavailable results and stage telemetry.
- Responsive browser checks at **320, 390, 480, 768, 1024, 1366 and 1600 px**
  found no page-wide horizontal overflow. Mobile drawer controls and Escape
  handling pass; final setup checks verify that launching remains visible while
  the fields scroll.
- No JavaScript page errors or external browser requests were recorded in the
  complete browser pass. Analysis submission was intercepted to verify the form
  payload without starting another satellite run.

Local QA artifacts are under `outputs/ui_redesign/`: browser verification JSON,
final screenshots, and the verification scripts. These are ignored local
artifacts, not new scientific evaluation evidence. The original scientific
submission gates in the master plan remain separate from UI verification.

Open the existing dashboard at `http://127.0.0.1:8000` and refresh to load the
updated static application.

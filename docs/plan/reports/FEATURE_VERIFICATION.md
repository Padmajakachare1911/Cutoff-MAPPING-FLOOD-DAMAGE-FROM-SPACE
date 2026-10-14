# Real pipeline and UI verification — 14 October 2026

Scope: verify the current P1/P2/P3/P4 implementation and its Streamlit integration, using released model-v1. No new model training, numerical threshold tuning, reference evaluation, project freeze or competition submission was performed.

## Bugs found and repaired

1. OSM requests exceeded the standard key's sliding limit (15 calls in 60 seconds). A real request returned 429; the legacy fallback returned 403. Pacing is now 4.2 seconds, tiles are 0.5 degrees without changing the AOI or 15 km buffer, and 429 retries wait at least 60 seconds or a longer numeric Retry-After. P4's matching fix and documented 240-second extraction timeout are incorporated.
2. Completing a dashboard run wrote widget state after widget creation, raising `StreamlitAPIException`. Completion now requests a new history selection for the next full render. The regression failed before the repair and passes afterward.
3. Adding another run changed history options and silently reset the selected run during subsequent scenario switching. Selection is now remembered outside the widget and restored when options change. The regression failed before the repair and passes afterward.
4. Intentional cached-mode OSM reuse emitted four misleading API-outage warnings. Matching cache reuse is logged normally; actual live failures still warn. The regression failed before the repair and passes afterward.
5. P4's south-case verification found a highway-tagged polygon passed into centreline routing. The published `p4/live-integration-unblock` fix excludes road areas from live parsing and dated caches, with regression coverage. Its history and three-case evidence are included in this integration.

V1 checkpoint SHA remains `a2701cfcfbaa1d6facba585cb835aeff95607dadf6d6647ce84cb1d7fe380d46`. V2 is excluded.

## Actual checks

- Supplied ohsome key loaded privately from `.env`; historical extraction returned HTTP 200. No credential values are committed or printed.
- Real Trishuli north: all production acquisition/terrain/S2/v1/change/gating/vectorize/OSM/settlements/exposure/access/report stages ran; all contracts pass, no partial state, no warnings, three scenarios and a one-page PDF. Run: `C:/cutoff_data/feature_verification/real_north_v1_fixed`. Warm satellite caches were reused; OSM was acquired live for the full routing extent.
- Real Deir: full run launched through the actual browser Run button; progress and completed-run selection passed. Five cached-mode OSM/noise warnings from the earlier run were retained as historical output. A fresh full rerun after warning repair has only the documented lowland change-noise warning. Run: `C:/cutoff_data/feature_verification/real_deir_v1_final`. Its matching historical OSM cache was acquired live on the May snapshot.
- Chromium browser checks on both real AOIs: A/B/C counts match `results.json`; Leaflet raster/vector layers render; no application exception or JavaScript error; PDF, hazard GeoPackage, selected settlements GeoPackage, hazard GeoTIFF and Results JSON all download byte-identically to pipeline files. Screenshots were visually inspected. Evidence: `C:/cutoff_data/feature_browser_results.json`.
- One-page real sitrep visually inspected; exposure/scenario counts and attribution are present. No fabricated accuracy or actual physical closure claim is made.
- P4's independently published north/south/Deir full-run evidence is preserved in `docs/results/P4_live_integration.json` and `P4_LIVE_INTEGRATION.md`. Those tests and timings describe that branch, rather than this combined head.
- Bounded flow-path component: real cached Copernicus DEM at 30 m plus a live historical OSM places query produced a 20.82 km downstream trace and nearby names. The generated optional layer passes its contract. This does not establish the full 150 km source-area trace or its geographic acceptance route.
- Final combined offline suite: **190 passed, 1 skipped, 4 deselected in 143.02 seconds**. This includes the P4 road-area/live-OSM tests and both new UI-history regressions. Log/XML: `C:/cutoff_data/feature_combined_final_tests.log` and `C:/cutoff_data/feature_combined_final_tests.xml`. Chromium evidence is recorded separately from pytest. The optional real flow-path layer also appears in the rendered Folium map.

## Verification boundaries

The core real pipeline is verified, including exposure/access that were previously partial. The browser checks supplement the automated offline suite rather than claiming that no possible bug exists. Fresh cold satellite acquisition and a fresh full SNAP download/processing run were not repeated; prior P1 SNAP acceptance remains historical evidence. Full-search bonus flow-path acquisition was not repeated, and the current UI displays an existing flow-path layer but has no source-coordinate input to start that optional CLI feature. These are explicit coverage limits.

The E4 harness remains tested with synthetic reference fixtures only; no real reference comparison was performed. Product verification does not certify v1's desert/gorge prediction accuracy.

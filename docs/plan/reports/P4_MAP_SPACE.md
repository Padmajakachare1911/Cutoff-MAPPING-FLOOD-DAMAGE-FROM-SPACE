# Map space and previous terrain view — 15 October 2026

The user accepted the new map story and asked for substantially more map space,
workspace controls in a navbar, information outside the canvas, and continued
access to the previous terrain presentation.

## Changes

- Saved runs, New analysis and Results/exports are in the top navbar. Run history
  and setup open in a responsive dialog with search, pagination, focus trapping,
  Escape/backdrop close and a submit button that stays visible as fields scroll.
  There is no permanently occupied workspace sidebar.
- The situation map spans the page. Settlement/access details are below it,
  using a horizontal layout on desktop and a stacked layout on phones.
- Dates, comparison slider, legend, interpretation and AI explanation are outside
  the canvas. Additional layers expand above it. A ResizeObserver reports the
  height of those rows to the parent so opening controls does not shrink the
  geographic canvas. The canvas targets 80% of viewport height, within practical
  desktop/mobile limits. Feature popups remain available when explicitly clicked.
- Previous 3D terrain is a separate selectable tab. Its renderer was preserved
  from the repository's original map implementation: Copernicus terrain,
  Sentinel-1, hazard/change tiers, exposed assets, inferred closures, settlement
  markers, model scores, optical water and computed flow. Its controls/legend
  also sit outside the canvas. The same saved inference outputs and A/B/C
  scenarios are used; no retraining or change to Results is involved.
- Both views support settlement navigation, run/scenario switching and reset.
  Locating a settlement from the panel below scrolls back to the map. The 3D
  view retains rotation/tilt and respects reduced motion for flow animation.

## Verification

The focused dashboard/raster/animation checks passed: 18 existing focused checks
plus coverage of the copied terrain animation, for 19 distinct checks. The
animation regression runs against both map implementations.

Playwright verified both real saved cases and both presentations, including
terrain/pitch, model-score controls, A/B/C retaining the terrain tab and returning
to the before/after view. At 1600 × 1000 the map card measured **1544 px wide**,
and the geographic canvas **800.86 px high**. Opening layers or AI explanation
kept the canvas height within 3 px; dates, legend and AI panel did not intersect
the canvas. Settlement access was below the map.

Responsive checks at 320, 390, 768, 1024 and 1920 px found no page-wide overflow.
Navbar dialogs and visible submit/Escape handling passed at each width. No page
errors were recorded. Screenshots and receipts are under ignored
`outputs/map_space/`; JavaScript syntax and `git diff --check` pass.

The previous terrain has the same finite DEM coverage and boundary artifacts as
the original presentation, noted beneath that view. The default map remains the
new, flat before/after presentation.

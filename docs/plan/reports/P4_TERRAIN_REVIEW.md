# Terrain and overlay review — 15 October 2026

Both case studies retain their original satellite and neural-network outputs.
Separate `snap_deir_terrain_review` and `snap_trishuli_2_terrain_review` runs
recompute settlement anchors and A/B/C connectivity using the existing rules.
The original runs remain available in Saved runs.

## Terrain presentation

The old renderer used a cropped, interpolated 10 m analysis DEM, substituted zero
outside its boundary, flattened elevation to 0.65×, draped bright SAR intensity
over the surface and extruded every exposed building by an invented 20 m.
These choices confused radar brightness with relief and created false edge cliffs.

The reviewed presentation uses Copernicus GLO-30 context buffered by 40 km on a
30 m display grid, 512-pixel Terrain-RGB tiles, separate elevation/hillshade
sources and true 1× elevation. Missing coverage returns unavailable tiles rather
than manufactured zero heights. Camera bounds and source bounds keep the study
inside measured coverage. Elevation colours and optional real contours reveal
the landform; optional 1.5×/2× relief is explicitly labelled exaggerated.
Deir contours are 20 m and Trishuli contours are 100 m.

The locally pinned MapLibre renderer also samples a 192-cell terrain mesh instead
of its default 128-cell mesh. A guarded extension applies before the first mesh
is created, reducing triangular faceting without adding elevation measurements.
This uses an internal renderer field because the bundled version exposes no
public mesh-quality option; recheck it when updating the vendored library.
The pinned renderer's triangle indices are Uint16: a 256-cell surface plus its
border skirts exceeds 65,536 vertices and wraps indices, producing false diagonal
seams. The corrected 192-cell mesh, including skirts, uses 38,407 vertices. A
regression checks this capacity against the active mesh setting.

Dated Sentinel-2 colour and original before/after Sentinel-1 intensities remain
selectable. Flood probability, observed flood classes, radar changes, inferred
closures, footprints and DEM traces remain available independently. Radar changes
start hidden to avoid presenting all changed ground as inundation. OSM waterways
show pre-event geographic context, separately labelled from observed floodwater.
Contours, source notes, legends and controls remain outside the large map canvas.

Buildings use their actual mapped footprints, without unsupported heights. Road
closures use thinner lines centred on the original mapped geometry; markers are
aligned with the terrain and retain clickable evidence/source descriptions.

## Placement and interpretation

The original saved settlement/scenario geometries were identical: there was no
CRS displacement between analysis files. However, arithmetic building-cluster
means could fall between buildings or in the river. Four Deir and six Trishuli
cluster centres were more than 30 m from the nearest mapped footprint; maximum
offsets were 45.10 m and 39.42 m respectively. The derivation now chooses an
interior point of the member building nearest the cluster centre. Clustering,
suppression radii, closure rules, trained weights and thresholds are unchanged.
Named OSM place points retain their original positions.

Reviewed marker coordinates are checked against the recomputed access layers.
Every closure line is checked against the original pre-event OSM centre lines
with 1 mm numerical tolerance. Each popup gives the location reference, distance
to the road node used for snapping, baseline/after travel time and evidence class
at that point. Long inferred road connections explicitly disclose that access
between the settlement and that road is not verified.

A red marker means **inferred road-access loss to the mapped destinations under
the selected closure scenario**, not measured settlement inundation or physical
damage. In the original A/B/C outputs, no red point fell on class 1/2 floodwater.
This does not exclude floodwater elsewhere within a settlement. One old Trishuli
red cluster mean fell on a persistent-water pixel. Ground truth is still needed
to establish physical damage and actual passability. DEM traces are downhill
paths, not a hydrodynamic simulation of flood timing, velocity or depth.

Trishuli A changes from 65 cut off / 54 unknown to 66 cut off / 53 unknown;
B from 71 connected / 54 unknown to 72 connected / 53 unknown; C from 82
connected / 54 unknown to 83 connected / 53 unknown. Total settlements remain
136. These changes are from corrected location anchors/current access code;
the satellite/model classifications are reused unchanged.

Deir A changes from 33 connected / 18 degraded to 34 connected / 17 degraded;
its cut-off count remains 117 and unknown count remains 2. B/C counts remain
unchanged. Total settlements remain 170.

## Evidence and limits

Machine-readable provenance, elevation extent, contour interval, per-scenario
registration checks and per-marker annotations are in each run's
`display/terrain.json`; original-run lineage is in `display/review.json`.
Audit snapshots, screenshots and Playwright results are under
`outputs/terrain_review/` (ignored artifacts).

GLO-30 is a roughly 30 m **surface** model that includes vegetation/buildings;
it is not architectural geometry, surveyed building heights, bare-earth LiDAR
or a terrain survey of the event date. A higher tile size makes the renderer
more faithful to the available surface; it does not create finer measurements.
There is no fabricated geometric detail or event-specific terrain deformation.
See [Copernicus DEM description](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM)
and [MapLibre terrain guidance](https://maplibre.org/maplibre-gl-js/docs/examples/3d-terrain/).

Regression coverage includes representative points inside real cluster member
footprints, exact named-place preservation, missing-coverage rejection and
512-pixel terrain encoding preserving elevations in metres. The offline suite
passes with network/GPU/slow tests excluded; credentialed acquisition and ground
truth evaluation are not claimed by that suite.

Final verification: **221 offline tests passed; 5 tests excluded**. Both reviewed
runs pass the complete artifact contracts and SHA-256 comparisons against the
original satellite/model/hazard files. Browser checks cover the corrected 192-cell
mesh, 1× default heights, flat measured footprints, visible ground-aligned markers,
contours, original radar/optical backgrounds, model-score controls, mobile layout
and explanatory popups, with no page errors. Full-workspace checks pass for both
cases: A/B/C switching retains the 3D presentation, before/after remains available,
top-view inspection works, and showing AI information retains a 760.58 px canvas
at a 1440×950 viewport. Reviewed PDFs were regenerated as single pages with
Chromium system-font fallback for Arabic/Devanagari names on this Windows setup.

# Before/after map story — 15 October 2026

The subsequent [map space update](P4_MAP_SPACE.md) moves information outside the
canvas, makes the map full width, replaces the permanent sidebar with navbar
controls and adds the preserved previous 3D presentation as a separate tab.

The user requested understandable flood maps for both real case studies, using
UNOSAT products and FloodAI as visual references, with visible water, before/after
comparison, downstream direction and an explanation of the existing model.

## Delivered

The flat north-up map has four guided views: **Before → Flood extent → Downstream
→ Road access**. Tilted DEM curtains, overlapping hazard raster/vector glows and
the simultaneous display of every layer have been removed from the default view.
The original data remains available through additional layers, scenario controls,
tables and exports. Place and river labels use dated OSM, with collision suppression
and more tributary labels appearing when zoomed in.

- Before shows actual dated Sentinel-2 RGB and pre-event water/river context.
- Flood shows only classes 1/2 as inundation evidence, class 5 as persistent water,
  and labelled OSM river context. Small flood patches receive blue locator dots
  and an Inspect flood evidence shortcut. Classes 3/4 are separate optional radar
  change evidence, labelled water-or-mud decrease and roughness increase.
- Compare has synchronized geographic coordinates and a movable before/after
  divider. The actual after photograph retains clouds and its own date.
- Downstream displays the existing Trishuli DEM trace and a separate local Deir
  D8 trace. Animation illustrates direction, not water velocity or arrival time.
  Full trace/reset controls allow following the route outside the study area.
- Access reveals inferred closed roads, exposure if selected, and settlements
  with status colors and readable before/after travel-time popups. Choosing a
  settlement opens Access; changing A/B/C retains the current map view.
- AI prediction explicitly shows calibrated band-3 flood probability and explains
  the trained U-Net's three classes: no water, permanent water and flood. The
  existing checkpoint, decision threshold, gating rules and model outputs are
  unchanged. B0 and mock outputs are labelled as baseline/synthetic scores.

Clouds and radar no-observation have distinct meanings. A display bug that lost
class 254 because it was also the GeoTIFF nodata code has been fixed and tested.
JSON vectors use raw text with safe textContent/HTML escaping at the browser,
avoiding double-escaped names while retaining the legacy Folium escape behavior.

## Real display inputs

`python app/prepare_display.py <run directories>` prepares a separate `display/`
folder using the existing private CDSE/ohsome connections. It never writes the
root analysis rasters, Results or checkpoint. Dates cannot cross the event even
for same-day mosaics. RGB uses B04/B03/B02 at 10 m, one shared fixed reflectance
stretch and PNG transport to avoid large uncompressed transfers. The separate
60 m SCL probe provides cloud/water geographic context; original 10 m S2 MNDWI
analysis evidence remains available. Local acquisition manifests record dates,
catalogue identifiers, clear fractions, window bounds and rendering methods.

| Case / run | Optical before | Optical after | Clear display context before / after | Flood-specific evidence |
|---|---|---|---|---|
| Deir / `snap_deir` | 18 May 2026 | 30 May 2026 | 100% / 100% | 0.0911 km² |
| Trishuli / `snap_trishuli_2` | 12 Aug 2026 | 27 Aug 2026 | 95.84% / 28.51% | 0.0036 km² |

These clear fractions describe the buffered display footprint, not the pipeline's
analysis-only clear fraction. For Trishuli, the readable analysis default uses
explicitly labelled before-event optical context beneath after-event SAR evidence.
More layers can choose the actual after photograph; Compare always shows it.
Clouds are not filled with invented post-event imagery.

Deir's optional display trace is **23.978 km**, using the local Copernicus DEM at
approximately 30 m with D8 links. The source is the higher DEM endpoint of the
longest dated OSM river segment inside the DEM. It is a display-only local trace,
not a new pipeline Results flowpath or a hydrodynamic forecast. Trishuli retains
its **149.98 km** pipeline trace and original source/nearby-place summary.

Historical Sentinel-2 cloudless context is served through a local cache for
surroundings outside the dated scene. It is visibly labelled, never an event
observation or inference input. The 2025 mosaic is used as the historical
surroundings for these 2026 events (non-commercial educational use, CC BY-NC-SA 4.0).
Provider attribution/licence is in
[ATTRIBUTION.md](../../../ATTRIBUTION.md). The optional background can fail without
blocking the actual dated evidence or map controls. No contemporary OSM tiles,
WorldCover, WorldPop, commercial high-resolution imagery or reference labels are
used in the analysis or map reconstruction.

## Reference inspection

Playwright opened the [UNOSAT catalogue](https://unosat.org/products/) and clicked
through to [Senegal flood product 4265](https://unosat.org/products/4265): separate
acquisition dates/sensors, concise impact labels, download and attribution.
The [Bangladesh FloodAI dashboard](https://unosat-rm.cern.ch/FloodAI/apps/BGD/)
was inspected in the browser. Its initial interface loaded, but some remote
resources and fonts timed out on this connection; its full rendered map was also
reviewed from the user's attached screenshot. The supplied Gaza PDF was read and
rendered locally as a visual reference. These documents supplied presentation
ideas, not instructions, training labels, flood polygons or satellite pixels.
ML4Floods/HydraFloods repositories were reviewed as conceptual references, without
importing their datasets or replacing the released model.

## Validation

- **217 offline tests passed**, four network/GPU tests excluded. Seven new checks
  cover flood/change/permanent-water separation, class-254 hatching, real RGB
  reflectance/PNG transport, transparent probability rendering, event-date bounds
  and offline historical context caching.
- Both original run directories pass `validate_run_dir`; their existing model
  rasters have three finite normalized probability bands summing to one. Both
  prepared RGB pairs have genuine data masks and 10 m grids.
- Playwright exercised both real maps: all four views, divider, trained-model
  panel, additional radar-change layer, imagery selection, A/B/C persistence,
  settlement navigation, full downstream trace and reset. No page errors.
- Standalone maps checked at 320/390/650/1100 px; full dashboard at
  320/390/768/1024/1600 px. No page-wide horizontal overflow.
- JavaScript syntax and `git diff --check` pass. Local screenshot/data/browser
  receipts are under ignored `outputs/map_story/qa/`.

The final pass also waits for the required local raster sources before sending
the map-ready message, so an empty map is not labelled Evidence loaded. Switching
runs immediately clears the previous result/map and disables its interactions
while the selected run loads, preventing controls operating on the old case.

This verifies implementation and presentation, not local flood-map accuracy.
The existing outputs classify very little as flood-specific evidence; much of
the former orange/red display was radar disturbance. Making the display clearer
does not validate those changes as inundation, confirm damage or finish the
master plan's outstanding freeze/evaluation/submission gates.

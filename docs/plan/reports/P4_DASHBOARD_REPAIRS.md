# Real dashboard repairs, 14 October 2026

The new PR #38 dashboard is the selected UI. Model-v1 remains the default;
model-v2 and the abandoned Streamlit repair branch are excluded.

## Failure and repairs

The screenshot's cached STAC error came from the empty repository cache rather
than the prepared external cache. The server now loads `.env` before resolving
`CUTOFF_CACHE_DIR` and `CUTOFF_OUTPUT_DIR`; the UI receives those configured paths.
Fast is the default for acquiring missing inputs. Cached deliberately refuses
unprepared AOI/event combinations. Analyses are serialized to protect GPU/memory.
Historical failures stay failed; new runs never overwrite old evidence.

- Backend JSON hazard totals exclude permanent water and no observation.
- Partial results have an explicit state/banner, unavailable exposure/access,
  and downloads/layers gated by successfully reported stage results.
- Map controls expose hatched no observation, pre/post VV, model flood score
  calibrated on global floods, and optional Sentinel-2 water.
- Provenance includes scene IDs, track, backend, post lag, S2 and OSM timestamp.
- Limitations are visible; evaluation is restricted to listed frozen runs.
- Terrain is generated from this run's Copernicus DEM. External Esri imagery and
  AWS Terrarium basemap datasets are removed; dated OSM roads remain visible.
- Flow visualization uses a computed `flowpath.gpkg` only. Source input,
  download, and zoom-to-path are connected. No polygon-derived substitute trace.
- MapLibre, Lucide and GSAP assets are bundled at the existing pinned versions,
  retaining their upstream notices, so CDN requests cannot block core rendering.
- Exact-date/grid/AOI/buffer/filter OSM caches can be reused across transport
  namespaces. Other dates or smaller routing buffers cannot satisfy a query.
- AOIs with no mapped roads produce unknown access, rather than a graph crash.
- The full optional trace caches its expanded 30 m DEM and exact dated places,
  enabling offline reproduction. Large DEM mosaics cache whole public COG tiles, resume interrupted downloads,
  and transfer independent tiles concurrently.

## Observed real browser evidence

Both analyses were launched through the actual dashboard form on this Windows
RTX 4050 machine, with released v1 and warm satellite inputs plus live dated OSM:

| Preset | Run ID | State | Hazard km² | A cut off | B cut off | C cut off |
|---|---|---|---:|---:|---:|---:|
| Trishuli | `20261014T162514_9657c9e8` | complete | 0.249 | 28 | 0 | 0 |
| Deir ez-Zor | `20261014T163030_714a9528` | complete | 10.479 | 77 | 0 | 0 |

Browser verification switched all scenarios and checked displayed counts against
Results, toggled pre/post/score/S2/no-observation controls, checked provenance and
limitations, loaded local terrain, downloaded PDF/GeoTIFF/GeoPackage/JSON, and
recorded no JavaScript page errors. Deir retains the documented lowland HAND
fallback warning; a complete pipeline does not establish model accuracy there.

Local full offline suite: **197 passed, 1 skipped, 4 deselected** before the final
DEM-cache addition. Its focused cache/flow/animation tests passed **4 tests**;
the final dashboard/DEM regressions passed **10 tests**. Linux/Windows CI also
includes the new dashboard and animation regressions.

A fresh cached pipeline run `20261014T165114_e6840ed8` completed with
no warnings and released model-v1.

Private artifacts are under `C:/cutoff_data`: `dashboard_real_launch_verification.json`,
`trishuli_repaired_dashboard.png`, `deir_repaired_dashboard.png`, and test logs.
Keys, model weights, caches, run exports and screenshots are not committed.

Full live downstream named-river acceptance is tracked separately from these
core dashboard passes; a synthetic trace test is not evidence for that route.
No new training, checkpoint selection, threshold tuning, project freeze, E4
reference evaluation, or final submission was performed.

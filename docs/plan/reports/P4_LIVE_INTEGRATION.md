# P4 live integration — issue #31

Verified on 14 October 2026 on `p4/live-integration-unblock`, based on main
`038c490`. The supplied private configuration was loaded into the ignored local
`.env`. CDSE OAuth authenticated and a real ohsome v2 extraction returned HTTP
200. No credentials are included in this report, Git or GitHub issues.

## Failure and repair

The original missing-key blocker was resolved by private configuration. The first
full run then exposed HTTP 429: the previous 0.5-second pacing could exceed the
standard extraction plan's 15 requests per minute, and 5/10-second retries could
expire before its sliding window cleared. The restricted v1 fallback returned
403, leaving a correctly labelled partial run.

The fix uses 4.1-second pacing, waits at least 60 seconds on a retryable 429 and
honours a longer numeric Retry-After. Extraction timeout now matches the
documented 240-second server limit. Query tiles are 0.5 degrees, reducing daily
quota use while preserving intersection with the exact AOI and full 15 km routing
buffer. Existing cache identities still bind the exact UTC snapshot, AOI, buffer
and filters. Model-v1, scientific thresholds and source dates are unchanged.

South's newly acquired roads also contained one highway-tagged polygon
(`way/523207700`). Routing expects centreline coordinates; this area caused
`Polygon.coords` to raise. Road parsing now excludes area geometries, and the
same check applies when loading existing dated caches. Two regression tests
cover live parsing and cache-to-network integration. The original dated south
OSM acquisition is retained, and its final pipeline rerun uses that matching
cache; no source date or coverage was substituted.

Sources: [HeiGIT standard plans](https://account.heigit.org/info/plans),
[sliding-window rate-limit explanation](https://giscience.github.io/openrouteservice/frequently-asked-questions#when-and-how-does-my-quota-reset),
[ohsome extraction timeout](https://docs.ohsome.org/ohsome-api/v2/reference/api.html).

## Acceptance evidence

Evidence is recorded in `docs/results/P4_live_integration.json`. Full run folders,
logs, results, GeoPackages and PDFs remain in ignored `outputs/`; dated caches
remain in ignored `cache/dated_osm/`. These are real model-v1 fast-mode runs with
warm satellite/DEM/S2 caches and historical OSM newly fetched through v2 (south's
final rerun reuses its matching newly acquired OSM cache). They are
not cold satellite acquisition or the E7 size sweep.

| Case | OSM date | Roads | Buildings | Places | Health | Cut off A / B / C | Wall time (s) |
|---|---|---:|---:|---:|---:|---|---:|
| north | 2026-07-27 | 2697 | 5703 | 216 | 12 | 28 / 0 / 0 | 136.44 |
| south | 2026-07-27 | 18552 | 61987 | 426 | 88 | 65 / 0 / 0 | 292.48 |
| deir | 2026-05-01 | 4668 | 5510 | 50 | 3 | 77 / 0 / 0 | 185.79 |

All three final runs have exposure and A/B/C access, pass all run contracts,
generate a one-page PDF, and load/switch scenarios in the real Streamlit app
without exceptions. Full offline suite: **188 passed, 1 skipped, 4 deselected**
in 98.18 seconds; focused OSM/pipeline suite: **31 passed**. E/F/I lint and
workflow YAML validation pass. South uses its fresh matching cache after excluding
one highway area. Deir retains its disclosed lowland noise-estimation warning;
unknown access stays unknown. The counts are model/scenario outputs, not verified
physical closures or damage.


## Reproduction

From the repository root, set working `SH_CLIENT_ID`, `SH_CLIENT_SECRET` and
`OHSOME_API_KEY` in the ignored `.env`, obtain the released v1 checkpoint and the
P1 satellite caches, then use fresh run IDs:

```text
cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --osm-snapshot 2026-07-27T00:00:00Z --run-id live_north --cache-dir cache
cutoff run --bbox 85.1,27.88,85.3,28.1 --event 2026-08-26T02:52:00Z --mode fast --osm-snapshot 2026-07-27T00:00:00Z --run-id live_south --cache-dir cache
cutoff run --bbox 40.05,35.25,40.25,35.40 --event 2026-05-25T00:00:00Z --mode fast --osm-snapshot 2026-05-01T00:00:00Z --run-id live_deir --cache-dir cache
```

The Deir snapshot must precede its May event; the default July snapshot is invalid
for this case. After acquisition, the same inputs/configuration and `--mode cached`
reuse the dated caches. Launch `streamlit run app/streamlit_app.py` and select the
completed run from Run history.

The new `P4 live integration guards` workflow runs the OSM/pipeline regression
suite on Linux and Windows without private keys. Live evidence does not replace
the separately pending independent fresh-clone rehearsal, intentional freeze,
E4, real E6/dropout measurements or cold E7. The video remains deferred.

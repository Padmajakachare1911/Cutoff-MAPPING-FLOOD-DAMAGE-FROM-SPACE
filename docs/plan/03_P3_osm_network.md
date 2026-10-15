# P3 — OSM, Exposure & Access stream (Person 3)

> **For agentic workers:** you answer "what was exposed?" and "who is cut off?" (20 % of the score), plus the bonus flow path. Read `00_MASTER_PLAN.md` and `05_contracts.md` first. Build and test everything against the mock run first (`python -m cutoff.mock outputs/demo_mock` has hazard polygons, roads, a bridge, villages, a hospital and an orphan hamlet). TDD, one PR per task.

**You deliver:**
- a pre-event OSM snapshot (date-guarded) on the run grid;
- settlements (OSM places + building clusters) and targets (health facilities, towns);
- exposure counts (exposed, never "damaged");
- a correctly noded road graph with closure scenarios A/B/C and four statuses;
- the bonus downstream flow path;
- experiment E6.

**Files you own:** `src/cutoff/data/osm.py`, `src/cutoff/geo/{settlements,exposure,network,flowpath}.py`, `eval/access_eval.py`, `tests/test_p3_*.py`, `tests/fixtures/ohsome_*.parquet`, `docs/results/E6.md`.

**Verified facts (2026-10-12):**
- **ohsome API v2:**
  - URL: `POST https://api.heigit.org/ohsome-api/v2-rc/extraction/features.parquet`, header `authorization: <OHSOME_API_KEY>` (free key, account.heigit.org).
  - JSON body: `{"aoi": <GeoJSON Polygon>, "filter": "<ohsome filter>", "time": "2026-07-27T00:00:00Z", "clip": false}`. A single timestamp returns a snapshot.
  - The response is GeoParquet: `geopandas.read_parquet(BytesIO(r.content), to_pandas_kwargs={"maps_as_pydicts": "strict"})`, then `pandas.json_normalize(df["tags"])`.
  - All properties are always returned.
- **ohsome API v1:** `POST https://api.ohsome.org/v1/elements/geometry` (`bboxes`, `time`, `filter`, `properties=tags`). It shuts down on **2026-11-30**; use it only as a fallback.
- v2 holds data newer than the event, so the snapshot time is **mandatory**. Sending `"latest"` or any time ≥ the event is a disqualification risk; `assert_pre_event` guards it.
- The ohsome filter language is the same in v1 and v2, e.g. `highway in (primary, secondary) and type:way`, `building=* and geometry:polygon`.
- Bonus: `pyflwdir.FlwdirRaster.path(xy=([x], [y]), direction="down", max_length=..., unit="m")` returns cell indices of the path.

---

### P3.0 Setup + ohsome recon (T+0 → T+2)
- [ ] Get an ohsome API key and put it in `.env`. Run `make test` (green).
- [ ] Make one v2 request for the Trishuli north AOI (85.28,28.10,85.42,28.29), filter `highway=* and type:way`, time `2026-07-27T00:00:00Z`.
  - Save a ≤ 1 MB sample as `tests/fixtures/ohsome_roads_sample.parquet`.
  - Record the exact column names (OSM id, type, tags, geometry, any validity timestamps) in `docs/plan/reports/P3.0.md`.
  - Repeat for buildings, places and health. Record the counts. Low counts are expected in Rasuwa; that is a finding to report.

### P3.1 OSM stage (T+2 → T+6) — **needed for C1**
**Files:** `src/cutoff/data/osm.py`, `tests/test_p3_osm.py`
```python
def assert_pre_event(snapshot_iso: str, event: datetime) -> None   # raises ValueError if snapshot >= event
def fetch_layer(aoi_wgs84: Polygon, layer: str, snapshot_iso: str, cfg) -> gpd.GeoDataFrame   # EPSG:4326
def stage_osm(ctx) -> dict
```
Layer filters (agreed):

| Layer | ohsome filter | Post-processing |
|---|---|---|
| roads | `highway in (motorway, trunk, primary, secondary, tertiary, unclassified, residential, service, track, path, footway, steps, bridleway, motorway_link, trunk_link, primary_link, secondary_link, tertiary_link) and type:way` | `tier` = road (motorway…residential, links, service), track (track), trail (path, footway, steps, bridleway); `bridge` = tag `bridge` not in (None, "no"); keep `layer`, `name`, `highway` |
| buildings | `building=* and geometry:polygon` | — |
| places | `place in (city, town, village, hamlet, isolated_dwelling, locality) and geometry:point` | — |
| health | `amenity in (hospital, clinic, doctors) or healthcare in (hospital, clinic, centre, doctor) or healthcare=* and geometry:point` | polygons → centroids; `kind` from the tags (health posts map to `health_post`) |

- [ ] v2 first. On HTTP error, retry with backoff ×3, then try v1 (same filter, `bboxes`, `properties=tags`). If that fails too, use only a matching cached copy from `cache/osm/<grid_hash>/<canonical_UTC_snapshot>/<AOI_buffer_filter_hash>/<layer>.parquet` with `ctx.warn`. Do not substitute another date or routing extent. If there is no matching cache, raise; the pipeline then marks the run partial.
- [ ] **Access extent:** fetch roads, places and health for the AOI **buffered by `cfg.access.access_buffer_km` (15 km)**, because a village's nearest hospital or town and the roads to it are often outside the hazard AOI. Fetch buildings for the AOI only. Hazard is known only inside the AOI, so roads outside it are assumed open; state that in the results limitations.
- [ ] Tile requests larger than `cfg.osm.tile_deg` (0.1°), dedupe by OSM id, reproject to the grid CRS, and write the four GPKGs with the contract columns (`osm_id` as `"way/123"`, etc.). Vectors may extend beyond the raster grid; only their CRS must match.
- [ ] Return `{"osm_snapshot", "osm_api", "counts"}`.
- [ ] Tests:
  - `assert_pre_event("2026-07-27T00:00:00Z", 2026-08-26T02:52Z)` passes, and `("2026-08-26T03:00:00Z", …)` raises;
  - **any call path with `time="latest"` raises** (grep the module in the test);
  - parsing the recorded parquet fixture yields the tier/bridge columns;
  - the v1 fallback is used when v2 returns 503 (mock httpx).

### P3.2 Settlements and targets, D7 (T+4 → T+8)
**Files:** `src/cutoff/geo/settlements.py`, `tests/test_p3_settlements.py`
- [ ] Settlements:
  1. Every OSM place point gets `source=osm_place` and `n_buildings` = buildings within 150 m.
  2. **Building clusters**: union of 40 m buffers around building centroids. Each connected blob with ≥ 5 buildings becomes a settlement at its centroid, `source=building_cluster`, named `"Unnamed settlement (<n> bldgs) near <nearest place name, if within 2 km>"`.
  3. Drop a cluster if a place point lies within 300 m of it, so the place keeps the name.
  4. `sid` = stable hash of the rounded coordinates.
- [ ] Targets: health facilities (`kind` from tags) + places with `place in (town, city)`, all from the 15 km access extent. Fields: `tid`, `name`, `kind`. If there is still no target, call `ctx.warn("no hospital/town within AOI + 15 km in pre-event OSM")`; every settlement then becomes `unknown`.
- [ ] Settlements are reported only **inside the AOI**; the buffer is used just for routing.
- [ ] Tests:
  - 6 buildings in a blob → 1 cluster;
  - 4 buildings → none;
  - a cluster next to a place point is merged into the place;
  - places outside the AOI are not settlements but can be targets.

### P3.3 Exposure stage (T+6 → T+9)
**Files:** `src/cutoff/geo/exposure.py`, `tests/test_p3_exposure.py`
- [ ] Buildings whose footprint intersects a hazard polygon get the **highest-priority** class they touch (order 1 > 4 > 3 > 2). Count them per class name.
- [ ] Roads: intersection length per class (km). Bridges: bridge ways within 15 m of the class. Write `exposure_buildings.gpkg` and `exposure_roads.gpkg` (with `hazard_class`, `length_m`).
- [ ] Vocabulary: column, dict and log names say `exposed`; never use the words damaged or destroyed.
- [ ] Tests: on the mock run, the 3 riverside houses are exposed and the village houses are not; road km match a hand calculation within 1 %.

### P3.4 Road graph, scenarios and statuses, D8 + D10 (T+4 → T+12) — **needed for C1 (scenario A at least)**
**Files:** `src/cutoff/geo/network.py`, `tests/test_p3_network.py`
```python
def node_ways(roads: gpd.GeoDataFrame, max_seg_m=100.0) -> gpd.GeoDataFrame
    # split EACH way at its intersections with other ways of the same grade, then densify to <= max_seg_m.
    # Grade rule: ways with bridge=True, tunnel, or a different `layer` are NOT split where they cross other ways;
    # they connect only at shared endpoints. Attributes are copied from the parent way (no spatial lookup).
def build_graph(segments, tiers=("road", "track")) -> nx.MultiGraph   # nodes = endpoint coords rounded to 1 m;
    # edge key = seg_id; attrs: length, t (s) from DEFAULT_SPEED_KMH, bridge, seg_id
def closed_segments(segments, hazard, scenario, cfg) -> set[int]
def access_status(G, settlements, targets, closed, cfg) -> gpd.GeoDataFrame
def edge_dropout(G, frac, rng) -> nx.MultiGraph
def stage_access(ctx) -> dict
```
- [ ] **Splitting:** for each way, `shapely.ops.split(way, MultiPoint(intersection points with other same-grade ways))`, then `shapely.ops.substring` pieces of ≤ 100 m. Do **not** use a spatial-index `covers` lookup to recover attributes (the blueprint bug, D10).
- [ ] **Scenarios** (hazard classes from `contracts`):
  - **A**: segment within 15 m of any class 1–4 polygon → closed.
  - **B**: ≥ 50 m of the segment inside high-confidence classes (1, 4) → closed.
  - **C** (bridges only): a bridge segment is closed only if a high-confidence polygon intersects a 25 m buffer around **either end of the bridge way** (its approaches), not the mid-span (D8). Permanent water (5) never closes anything.
  - In A and B, bridges also follow D8: **high-confidence classes (1, 4)** must reach an approach; classes 2/3 and plain mid-span intersections do not close a bridge.
- [ ] **Status:**
  1. Snap each settlement and target to the nearest graph node within `snap_max_m` (500 m); unsnapped → `unknown`.
  2. Run multi-source Dijkstra from all targets on G (baseline `t0`) and on G minus the closed keys (`t1`).
  3. Assign: `unknown` if there is no baseline route; `cut_off` if there is no post route; `degraded` if `t1 > 1.5·t0`; else `connected`.
- [ ] Trails: build a second graph that also includes trails, only to flag cut-off settlements that still have a **trail** route. Add column `trail_access` (bool) to `settlements_{S}.gpkg` and mention it in the sitrep. It does not change `status`, because the PS asks about roads.
- [ ] `stage_access` writes `settlements_{A,B,C}.gpkg` and `roads_status_{A,B,C}.gpkg`, and returns `access` as `ScenarioResult` dicts: counts, cut-off/degraded lists in lon/lat, `closed_road_km`, `closed_bridges`.
- [ ] Tests (port blueprint §18.16 `_toy_network` and extend it):
  - a 4 km way crossed by a side road is split at the crossing, so a 230 m hazard closes 4 pieces, not the whole way;
  - statuses West = connected, East = cut_off, Orphan = unknown;
  - **a bridge over a hazard that touches only mid-span stays open in C; a hazard touching an approach closes it**;
  - a road passing **under** a bridge (different layer) is not noded to it;
  - parallel ways between the same nodes are both kept (MultiGraph) and closing one leaves the other;
  - `degraded` appears when a detour is > 1.5×;
  - the mock run passes the validator after `stage_access`.

### P3.5 Bonus: downstream flow path (T+14 → T+22)
**Files:** `src/cutoff/geo/flowpath.py`, `tests/test_p3_flowpath.py`
- [ ] `trace_flowpath(ctx, lon, lat)`:
  1. Fetch GLO-30 at 30 m over a bbox around the point, extended 1.0° downstream-agnostic (all directions), using P1's `cutoff.data.dem.dem_on_grid` on a 30 m UTM grid.
  2. Build `pyflwdir.from_dem(...)` and snap the start point to the nearest cell with upstream area > 1 km².
  3. `flw.path(xy=..., direction="down", max_length=150_000, unit="m")`.
  4. Convert to a LineString, then list OSM places (pre-event snapshot, queried along the path buffer) within 500 m of it.
  5. Write `flowpath.gpkg` and return a `FlowPath` dict.
- [ ] Acceptance (Trishuli): from the source area on the north flank of Langtang Himal (≈ 28.25 N, 85.52 E; read the exact coordinates off the DEM), the path should follow Lhende Khola → Bhote Koshi → Trishuli and pass near Syapru Besi and Betrawati. Record a map PNG in `docs/plan/reports/P3.5.md`.
- [ ] Test on a synthetic tilted valley: the path ends at the outlet and lists the settlements along it.

### P3.6 Experiment E6: cut-off robustness (T+20 → T+32)
**Files:** `eval/access_eval.py`, `docs/results/E6.md`
- [ ] (i) The synthetic-graph unit tests (P3.4) are the correctness evidence; cite them.
- [ ] (iii) On the frozen Trishuli run, build a table per scenario A/B/C: closed road km, closed bridges, and counts of connected/degraded/cut_off/unknown, plus the Jaccard of cut-off sets vs A.
- [ ] (iv) OSM-completeness sensitivity: 20 runs each of 10 % and 20 % random edge dropout. Report the status flip rate per settlement and the share of settlements whose status is stable in ≥ 80 % of runs.
- [ ] (ii) **After FREEZE only** (check-only, in `eval/`): compare our closed road/bridge segments with any EMSR927 transport-damage features within 25 m. Report precision/recall per scenario, and if EMSR927 has no transport layer, say so. Never feed this back into the rules.

### Hand-offs
- **To P4 at C1 (T+10):** `osm`, `settlements`, `exposure` and `access` (scenario A at minimum) merged and validated on the mock run and on Trishuli.
- **To P4 by T+24:** scenarios B and C with trail flags; by T+30, the E6 table and the bonus flow path for the video.

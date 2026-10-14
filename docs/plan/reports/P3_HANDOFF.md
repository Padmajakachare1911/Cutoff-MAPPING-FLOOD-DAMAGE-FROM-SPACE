# P3 hand-off

## Implemented

- Pre-event OSM v2 extraction, three-attempt retry, v1/cache fallback, tiling, deduplication, 15 km access extent,
  normalization, and all four contract outputs.
- OSM places plus building-cluster settlements and health/town/city targets.
- Per-class building, road, and bridge exposure.
- Correctly noded keyed road multigraph, scenarios A/B/C, four access statuses, and trail-access flags.
- Optional DEM downstream flow path and nearby-place listing.
- E6 scenario/Jaccard and deterministic 10%/20% edge-dropout evaluation tooling.

## Verification

- `python -m pytest tests -k p3 -q` → 21 passed.
- `python -m pytest -m "not network and not gpu" -q` → complete suite passed with one expected skip.
- Ruff passes on every P3 source, evaluation, and test file.
- All implemented stages have mock-run contract validation coverage.

## External prerequisites still open

1. Produce a real Trishuli run, then record the flow-path acceptance map and measured E6 table.
2. Create the project-level `frozen-v1` tag before running the explicitly post-freeze external transport check.

P3.0 v2 reconnaissance is complete. The checkout still has no cached P1/P2 inputs, run outputs, or `frozen-v1` tag.

## 14 October integration update

The statement above records the original handoff environment. The current laptop has real P1 caches and partial real P4 runs, but no complete verified dated OSM routing cache and no local `OHSOME_API_KEY`. Actual full-run acceptance and real E6 remain pending; see [TEAM_REMAINING_WORK.md](TEAM_REMAINING_WORK.md).

The direct OSM stage now binds cache identity to the exact UTC snapshot (including fractional seconds), AOI, routing buffer and layer filters. Only matching cached data may replace a failed API request. The unsafe cross-date fallback from the latest team main update was removed; older caches need verified provenance and reacquisition rather than automatic migration. The stable ohsome v2 endpoint replaces `/v2-rc`. All 13 focused OSM tests passed, including other-date rejection and matching-cache reuse.

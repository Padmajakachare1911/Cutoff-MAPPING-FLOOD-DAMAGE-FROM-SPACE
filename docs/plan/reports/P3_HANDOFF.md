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

1. Supply `OHSOME_API_KEY` and complete P3.0 live v2 schema/count reconnaissance and ≤1 MB fixtures.
2. Produce a real Trishuli run, then record the flow-path acceptance map and measured E6 table.
3. Create the project-level `frozen-v1` tag before running the explicitly post-freeze external transport check.

The checkout currently has no key, cached inputs, run outputs, or `frozen-v1` tag. The unauthenticated v1 request
was attempted and returned HTTP 403.

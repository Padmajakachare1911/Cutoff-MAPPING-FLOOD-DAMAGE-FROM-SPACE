# Data attribution (required in every submission artefact)

These strings are copied verbatim from the Track B problem statement. They appear in the README, the dashboard footer, every situation report, and the written report. `tests/test_contracts.py` checks them, and the pipeline refuses to write a `results.json` that lacks them.

- "Contains modified Copernicus Sentinel data 2026."
- "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."
- "© OpenStreetMap contributors."

## Training dataset
- Kuro Siwo: N. I. Bountos et al., "Kuro Siwo: 33 billion m² under the water. A global multi-temporal satellite dataset for rapid flood mapping", NeurIPS 2024 Datasets & Benchmarks, pp. 38105–38121, arXiv:2311.12056. Data CC BY 4.0, code MIT.
- Sen1Floods11 (only if the optional E9b ablation runs): D. Bonafilia et al., CVPR Workshops 2020, doi:10.1109/CVPRW50498.2020.00113.

## Check-only reference (never an input)
- Copernicus EMS EMSR927: "European Union, Copernicus Emergency Management Service data". Used only by `eval/`.

## OpenStreetMap licence
OSM-derived files that we publish (exposure and settlement layers) stay under ODbL 1.0 and carry "Contains OpenStreetMap data, ODbL 1.0 - © OpenStreetMap contributors."

## Historical display context

The map uses the Sentinel-2 cloudless 2025 mosaic solely for geographic
context outside the dated scene footprint. It is not an event observation,
training dataset, analysis input or contemporary infrastructure basemap.

Attribution shown alongside the map: "EOxCloudless — https://cloudless.eox.at by
EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2025)".
The mosaic is [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
for this non-commercial educational prototype; the code remains separately licensed.
See [provider terms](https://maps.eox.at/) and [release licence](https://cloudless.eox.at/documentation/license).
Only the Sentinel-2 cloudless layer is requested; the provider's terrain, labels,
population and other basemap products are not used. Dated RGB and river context
under `display/` retain their own acquisition/snapshot provenance.

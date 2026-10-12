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

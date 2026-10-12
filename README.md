# Cutoff — Mapping Flood Damage from Space

**Multimodal AI Hackathon 2026 · Track B.** Given any area and flood date, Cutoff uses free satellite data to answer three questions for rescue teams:

1. **Where did the flood hit?** Same-track Sentinel-1 radar change, a U-Net trained on Kuro Siwo, a statistical debris/mud change rule and terrain gating (radar shadow, slope, HAND), with Sentinel-2 as optical evidence when the sky is clear.
2. **What was exposed?** Buildings, roads and bridges from pre-event OpenStreetMap that lie inside the mapped hazard. These are reported as *exposed*, never as *damaged*.
3. **Who is cut off?** A noded road graph run under three closure scenarios. Each settlement gets one status: connected, degraded, cut off, or unknown (no mapped route).

The output is a map dashboard plus a one-page situation report, both generated from a single `results.json`. The case study is the 26 August 2026 Bhote Koshi–Trishuli flood, compared against Copernicus EMS EMSR927 as a check only.

> Educational prototype — not an operational tool.

## Status
**Phase 0 (contracts) is done. The build is in progress.** The team plan is in [`docs/plan/00_MASTER_PLAN.md`](docs/plan/00_MASTER_PLAN.md):

| Stream | Plan |
|---|---|
| P1 Data & SAR | [`docs/plan/01_P1_data_sar.md`](docs/plan/01_P1_data_sar.md) |
| P2 ML & Hazard | [`docs/plan/02_P2_ml_hazard.md`](docs/plan/02_P2_ml_hazard.md) |
| P3 OSM & Access | [`docs/plan/03_P3_osm_network.md`](docs/plan/03_P3_osm_network.md) |
| P4 Product & Integration | [`docs/plan/04_P4_product.md`](docs/plan/04_P4_product.md) |
| Interfaces | [`docs/plan/05_contracts.md`](docs/plan/05_contracts.md) |
| Verified facts + sources | [`docs/plan/06_verification_log.md`](docs/plan/06_verification_log.md) |
| How to drive the coding agents | [`docs/plan/07_agent_playbook.md`](docs/plan/07_agent_playbook.md) |

## Quickstart (developers)
```bash
conda env create -f environment.yml && conda activate cutoff
pip install -e ".[dev,app,pdf]"          # add ,ml for torch + segmentation-models-pytorch
cp .env.example .env                       # fill in your own keys
make test                                  # contract tests must be green
python -m cutoff.mock outputs/demo_mock    # synthetic, contract-valid run folder to build against
```

Once the build is finished, this will run the case study:
```bash
cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z --mode fast --model models/cutoff_unet_v1.pt
streamlit run app/streamlit_app.py
```

## Data rules
- **Inputs:** only Sentinel-1, Sentinel-2, Copernicus DEM (GLO-30), OpenStreetMap as of 2026-07-27, and the Kuro Siwo training dataset.
- **Check-only:** Copernicus EMS / UNOSAT maps and post-event OSM. They live in the git-ignored `reference/` folder and are read only by `eval/` after the `frozen-v1` tag.
- **Enforcement:** CI runs `tests/test_contracts.py::test_no_reference_leak` on every PR.

## Attribution
See [ATTRIBUTION.md](ATTRIBUTION.md).
- "Contains modified Copernicus Sentinel data 2026."
- "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."
- "© OpenStreetMap contributors."
- Kuro Siwo: Bountos et al., NeurIPS 2024 (CC BY 4.0).

## Licence
Code: MIT ([LICENSE](LICENSE)). Data: see ATTRIBUTION.md.

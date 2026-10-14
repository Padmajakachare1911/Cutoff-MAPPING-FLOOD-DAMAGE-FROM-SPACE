# Cutoff - Mapping Flood Exposure and Access from Space

**Multimodal AI Hackathon 2026, Track B.** Given a bounding box and event datetime,
Cutoff maps flood/change evidence, exposed infrastructure and possible loss of road
access. **Educational prototype - not an operational tool. Exposure is not confirmed damage.**

Workflow: same-track Sentinel-1 → radar preprocessing → Copernicus terrain + optional
post-event Sentinel-2 → U-Net/B0 + disturbance + terrain gating → pre-event OSM
exposure → A/B/C access scenarios → `results.json` → dashboard and one-page PDF.
P1-P3 stages are implemented; P4 connects them and produces the product/evaluation.
See [P4 workflow](docs/plan/reports/P4_WORKFLOW.md) and [task plan](docs/plan/04_P4_product.md).

## Quickstart

Python 3.11+. Use a clean environment to avoid preinstalled GDAL/MKL conflicts.

```bash
conda env create -f environment.yml
conda activate cutoff
python -m pip install -e ".[dev,app,pdf,ml]"
cp .env.example .env
make test
make mock
make app
```

Without conda/make, supported platforms can use Python wheels:

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev,app,pdf]"
python -m pytest -m "not network and not gpu"
python -m cutoff.cli mock outputs/demo_mock
python -m streamlit run app/streamlit_app.py
```

The synthetic demo verifies interfaces/product behaviour, not model accuracy.
WeasyPrint automatically falls back to xhtml2pdf when native libraries are absent.
The dashboard launches a CLI subprocess, tails stage logs, offers run history,
scenario switching, map evidence popups, Results tables and downloads. No current
basemap tiles are used as evidence. Trained inference requires the `ml` extra;
CPU torch/torchvision should come from the same [PyTorch index](https://pytorch.org/get-started/locally/).

## Run real case studies

Download the final model (or choose `--model b0`):

```bash
gh release download model-v1 --repo Padmajakachare1911/Cutoff-MAPPING-FLOOD-DAMAGE-FROM-SPACE \
  --pattern cutoff_unet_v1.pt --dir models
```

Expected SHA-256:
`a2701cfcfbaa1d6facba585cb835aeff95607dadf6d6647ce84cb1d7fe380d46`.
Get P1's [shared cache](https://drive.google.com/drive/folders/1wKf934-rm5wE4lyV1n39vK6ZUly_OwWA?usp=sharing)
or acquire your own with `scripts/cache_aoi.py`. Put `s1/`, `dem/`, `s2/` directly
under `cache/`, or pass `--cache-dir PATH`. Cached mode also requires OSM acquired
through the pipeline for the exact date/settings. Undated legacy OSM caches are
refused to prevent snapshot leakage. A first fast run needs your `.env` Sentinel Hub
credentials and an ohsome key (v1 fallback). Existing scenes can satisfy fast mode;
label those timings **warm cache**, not cold live acquisition.

```bash
cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z \
  --mode fast --model models/cutoff_unet_v1.pt --run-id trishuli_north
cutoff run --bbox 85.28,28.10,85.42,28.29 --event 2026-08-26T02:52:00Z \
  --mode cached --model models/cutoff_unet_v1.pt --run-id trishuli_north_cached
cutoff run --bbox 40.05,35.25,40.25,35.40 --event 2026-05-25T00:00:00Z \
  --osm-snapshot 2026-05-01T00:00:00Z --mode fast --model b0 --run-id deir_ez_zor
```

The May event needs an earlier OSM snapshot. Bare event dates mean 23:59:59 UTC
with a warning. Existing run folders are never overwritten. Same-track acquisition
failure exits 2 and writes error.json. Optional S2 failure continues; OSM/access
failure publishes a partial hazard report. `--stages` requires a dependency-complete
subset; input-only subsets write summaries without Results. `--flowpath LON,LAT`
needs network; cached mode warns/skips this current P3 implementation.

Full mode requires local ESA SNAP, CDSE login and SNAP_GPT; replace `--mode fast`
with `--mode full`. Competition acceptance of fast processing/caches is
[unconfirmed](docs/plan/reports/organiser_answers.md).

## Reproduce training and evaluation

See [P2 handoff](docs/plan/reports/P2_HANDOFF.md), [measured Kuro results](docs/results/P2_kuro_results.md),
[training config](configs/train_unet.yaml) and [P1 experiments](docs/plan/reports/P1.8.md).

```bash
cutoff train --config configs/train_unet.yaml --seed 42
cutoff eval-kuro --checkpoint models/cutoff_unet_v1.pt --strata slope --split test
python eval/access_eval.py outputs/trishuli_north --out outputs/trishuli_north/access_eval.json
```

The eval adapter translates checkpoint to P2's native models argument; slope strata
are always computed. Training/evaluation need the external Kuro store (`CUTOFF_DATA_DIR`)
and repository checkout. E4 is check-only in `eval/emsr927.py`; it refuses dirty or
non-frozen code and repeat evaluation. Freeze only after integration/model/config
checks. The dashboard Evaluation tab requires a run listed in frozen_runs.txt.

## Data rules and attribution

Inputs: S1, S2, Copernicus DEM GLO-30, strictly pre-event OSM and Kuro Siwo training
data. EMS/UNOSAT/post-event OSM are check-only after freeze and live in ignored
`reference/`. CI enforces the source leak guard. Secrets/cache/outputs are ignored.
No victim imagery is needed. Complete notices: [ATTRIBUTION.md](ATTRIBUTION.md).

- Contains modified Copernicus Sentinel data 2026.
- Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and
  Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA;
  all rights reserved.
- © OpenStreetMap contributors. Derived exports carry ODbL notice.
- Kuro Siwo: Bountos et al., NeurIPS 2024, CC BY 4.0.

## Limitations

Overpass timing can miss the peak; this is not early warning. Ten-metre pixels miss
many small roads/bridges. Shadow/layover/missing data are no observation. Wet mud
may resemble water; rough debris is statistical change. Surface DEM/gorge errors
and steep permanent-water artefacts remain possible. Lowland-heavy training limits
Himalayan transfer: model scores are not verified Himalayan probabilities. Access
depends on incomplete OSM; unknown is unmapped, not safe.

## Team and licence

P1 Data/SAR, P2 ML/Hazard, P3 OSM/Access, P4 Product/Integration. Ownership/contracts:
[master plan](docs/plan/00_MASTER_PLAN.md), [interfaces](docs/plan/05_contracts.md).
Task reports accompany feature PRs; check integration/submission evidence before
judging. Code: [MIT](LICENSE). Data retain their upstream licences.

# Cutoff - common commands. Windows users: run the same commands in Git Bash, or call them directly.
PY ?= python
AOI_TRISHULI = 85.28,28.10,85.42,28.29
EVENT_TRISHULI = 2026-08-26T02:52:00Z

.PHONY: setup test mock run-trishuli app eval-kuro eval-emsr freeze

setup:            ## conda env create -f environment.yml first; then:
	$(PY) -m pip install -e ".[dev,app,pdf]"

test:             ## unit + contract tests (no network, no GPU)
	$(PY) -m pytest -m "not network and not gpu"

mock:             ## synthetic contract-valid run for UI/report/network development
	$(PY) -m cutoff.mock outputs/demo_mock

run-trishuli:     ## case study (cached mode needs cache/ prepared by P1)
	cutoff run --bbox $(AOI_TRISHULI) --event $(EVENT_TRISHULI) --mode cached --model models/cutoff_unet_v1.pt

app:
	streamlit run app/streamlit_app.py

eval-kuro:        ## E1/E2/E3/E8 (P2)
	cutoff eval-kuro --checkpoint models/cutoff_unet_v1.pt --strata slope

eval-emsr:        ## E4 - ONLY after `git tag frozen-v1` (P4)
	git describe --tags --exact-match HEAD | grep -q frozen-v1 || (echo "tag frozen-v1 first" && exit 1)
	$(PY) eval/emsr927.py --run outputs/trishuli_frozen --reference reference/EMSR927

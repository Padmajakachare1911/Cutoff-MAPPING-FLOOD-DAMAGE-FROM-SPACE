Flood Mapping & Geospatial AI
Repository Investigation Report
Sentinel-1/2 | Kuro Siwo | Sen1Floods11 | SAR Change Detection | Infrastructure Impact | OSM Road Accessibility | Copernicus DEM | Geospatial AI Dashboards
Generated: 2026-10-10 | Investigator: Antigravity AI | 9 Repositories Investigated | 7 Topic Areas Covered
#1 ImpactMesh #2 KuroSiwo #3 Prithvi EO-2.0 ! Key Gap
IBM/ImpactMesh Orion-AI-Lab/KuroSiwo NASA-IMPACT/hls-foundation-os No End-to-End System Exists
Only repo with S1+S2+DEM+EMS labels. Best SAR segmentation code + weights. SOTA optical foundation model. Grounded reporting, OSM overlay,
Apache-2.0. pip-installable. MIT. Actively maintained 2026. Apache-2.0. HuggingFace demo live. dashboard: absent from ALL repos.

Flood Mapping & Geospatial AI | Repository Investigation Report
Flood Mapping & Geospatial AI - Repository Investigation Report
Generated: 2026-10-09 | Investigator: Antigravity AI
Executive Summary
No single public repository covers the full hackathon brief end-to-end. The strongest
individual-component baselines are Kuro Siwo (SAR flood segmentation) and
IBM/ImpactMesh + Prithvi (multimodal, DEM-aware, foundation-model ready).
The closest integrated competitor to the full brief is a manually assembled pipeline
combining several of the repositories below - no single team has shipped all seven
components in one open codebase.
1. Comprehensive Comparison Table
Tier 1 - Core SAR / Flood Segmentation Baselines
Attribute Kuro Siwo Sen1Floods11 ETCI-2021
URL Orion-AI-Lab/KuroSiwo cloudtostreet/Sen1Floods11 sidgan/ETCI-2021-Competition-on-Flood-Detection
Last code push 2026-07-16 Active 2021-04-09 Stale 2022-06-19 Stale
Stars / Forks 87 / 17 258 / 60 182 / 39
Open issues 9 13 (unanswered) 1
License MIT None stated Apache-2.0
Language Python Jupyter Notebook Jupyter Notebook
Dataset implemented 43 flood events, GRD + SLC, multi-temporal; v2 updated 2024 4,831 chips (512x512), 11 events, 6 continents; S1 GRD + S2 hand ETCI 2021 competition data (Sentinel-1 GRD, global)
labels
Data acquisition Shell script + Dropbox + HuggingFace GeoTIFFs + webdatasets gsutil rsync gs://sen1floods11 (~14 GB) External download from competition host
Preprocessing Yes - normalization constants, webdataset format Yes - COG-spec GeoTIFFs, STAC catalog Partial - normalization in notebooks
Training script Yes - full training loop with configs Jupyter notebooks only (Train.ipynb) Jupyter notebooks + scripts; cyclical pseudo-labeling
Inference script Yes - BlackBench evaluation suite No standalone inference script Inference notebook present
Model architectures U-Net, ResNet-50/101, ViT variants via config FCN, LogReg, Random Forest (comparison) U-Net with semi-supervised extensions
Pretrained weights Yes - HuggingFace checkpoints Yes - GCS bucket pretrained_models/ No public weights
SAR change detection YES - multi-temporal pre/co-event pairs NO - uni-temporal only NO - uni-temporal only
Page 1

Flood Mapping & Geospatial AI  |  Repository Investigation Report
|     | Attribute |     | Kuro Siwo |     | Sen1Floods11 |     | ETCI-2021 |
| --- | --------- | --- | --------- | --- | ------------ | --- | --------- |
Sentinel-2 fusion NO - SAR only YES - labels derived from S2 NO - SAR only
| Copernicus DEM         |     | NO  |     | NO  |     | NO  |     |
| ---------------------- | --- | --- | --- | --- | --- | --- | --- |
| OSM road accessibility |     | NO  |     | NO  |     | NO  |     |
| Infrastructure impact  |     | NO  |     | NO  |     | NO  |     |
| Geospatial dashboard   |     | NO  |     | NO  |     | NO  |     |
| Grounded reporting     |     | NO  |     | NO  |     | NO  |     |
Geographic assumptions Global; no hardcoded region; VV+VH polarization assumed Global; 6 continents; 512x512 px chips Global; chip-based; no tiling logic
Evaluation data BlackBench held-out test; IoU/F1/precision/recall Separate hand-labeled test set; IoU in paper Competition leaderboard; F1 reported in paper
Reproducibility HIGH - config files, seeds, eval scripts present MEDIUM - data accessible; training code minimal MEDIUM - notebooks work but competition-env dependent
Key dependencies PyTorch, torchvision, wandb, webdataset, gdal TensorFlow/Keras (older), gsutil PyTorch, segmentation-models-pytorch, albumentations
Hardware requirements GPU recommended (A100 tested; V100 feasible) CPU for experiments; GPU for training GPU (V100; ~12h training)
Setup difficulty MEDIUM - clear README, conda env HARD - GCS download + notebook-first MEDIUM - requirements.txt available
Tier 2 - Multimodal and Foundation Model Repos
Attribute IBM/ImpactMesh NASA-IMPACT/hls-foundation-os (Prithvi) UrbanSARFloods
URL IBM/ImpactMesh NASA-IMPACT/hls-foundation-os jie666-6/UrbanSARFloods
Last code push 2026-09-25 Very active 2025-07-18 Active 2026-01-06 Active
| Stars / Forks |     | 15 / 3     |     | 407 / 97         |     | 41 / 3       |     |
| ------------- | --- | ---------- | --- | ---------------- | --- | ------------ | --- |
| Open issues   |     | 0          |     | 34               |     | 4            |     |
| License       |     | Apache-2.0 |     | Apache-2.0       |     | NONE STATED  |     |
| Language      |     | Python     |     | Jupyter Notebook |     | Dataset only |     |
Dataset 400+ events; S1 + S2 + CopDEM; 4 temporal obs; Copernicus EMS Sen1Floods11 (fine-tuning); HLS multi-spectral (pre-training) 8,879 chips; 18 events; SLC intensity + InSAR coherence
labels
Data acquisition hf download ibm-esa-geospatial/ImpactMesh-Flood; Zarr v2 GCS bucket + NASA EarthData HuggingFace Dataset4EO earthflow/UrbanSARFlood
Preprocessing YES - Zarr dataloaders, TerraTorch normalization configs PARTIAL - pre-tiled chips; normalization in config MINIMAL - dataset README only
Training script YES - terratorch fit --config configs/... YES - MMSegmentation YAML configs NO
Inference script YES - terratorch test YES - notebook + HuggingFace Spaces demo NO
Model architectures TerraMind ViT; any TerraTorch encoder Prithvi ViT-MAE 100M/300M; UperNet/FPN decoder U-Net, DeepLabV3+ (via SMP; not provided)
Pretrained weights Via TerraTorch (auto-download) HuggingFace: NO weights
ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL-Sen1Floods11
SAR change detection YES - 4-timestamp multi-temporal NO - optical only YES - InSAR coherence
Sentinel-2 fusion YES - S1 + S2 + DEM fused YES - optical only (HLS = Landsat + S2) NO - SAR only
| Copernicus DEM         |     | YES - 4th modality in training |     | NO  |     | NO  |     |
| ---------------------- | --- | ------------------------------ | --- | --- | --- | --- | --- |
| OSM road accessibility |     | NO                             |     | NO  |     | NO  |     |
Page 2

Flood Mapping & Geospatial AI  |  Repository Investigation Report
Attribute IBM/ImpactMesh NASA-IMPACT/hls-foundation-os (Prithvi) UrbanSARFloods
Infrastructure impact PARTIAL - Copernicus EMS building damage labels NO NO
| Geospatial dashboard | NO  | HuggingFace Spaces demo only | NO  |
| -------------------- | --- | ---------------------------- | --- |
| Grounded reporting   | NO  | NO                           | NO  |
Geographic assumptions Global; no hardcoded bbox; DEM resolution varies by tile HLS UTM projection; 224x224 px hardcoded Global; 5 continents; 512x512 chips
Hardcoded params num_classes: 3 (flood), 2 (fire); Zarr chunk sizes 6-band input (B02,B03,B04,B8A,B11,B12); 224x224 px mandatory None (dataset only)
Evaluation data HuggingFace test split; terratorch test gives IoU/F1 Sen1Floods11 test set; IoU in HuggingFace model card Paper benchmark split; no evaluation script
Reproducibility HIGH - pip installable, config-driven MEDIUM - 34 open issues; env setup painful LOW - no training code
Key dependencies terratorch==1.2.1, zarr==2.18.0, numcodecs==0.15.1 mmsegmentation, mmcv, torch (pinned older versions) N/A
Hardware requirements GPU; >=16GB VRAM for TerraMind fine-tuning A100 used; V100 feasible N/A
Setup difficulty LOW - pip install works HARD - mmseg version conflicts in issues LOW (data only)
Tier 3 - Operational and Domain-Specific Tools
Attribute Sentinel1-Flood-Finder S1GFlood-Detection (DAM-Net) OSMnx
URL cordmaur/Sentinel1-Flood-Finder Tamer-Saleh/S1GFlood-Detection gboeing/osmnx
Last code push 2024-07-15 Slowing UNKNOWN (README 404 at investigation) Actively maintained
| Stars / Forks | 38 / 5                 | Unknown | ~5k / ~800 |
| ------------- | ---------------------- | ------- | ---------- |
| License       | GPL-3.0 COPYLEFT       | Unknown | MIT        |
| Language      | Python (Jupyter-heavy) | Python  | Python     |
Core capability Random Forest flood detection on Planetary Computer; no deep ViT bi-temporal change detection (DAM-Net); 5,360 S1 pairs OSM street network download, graph analysis, routing
learning
Data acquisition MS Planetary Computer API (auto) GCS or direct download Overpass API (auto)
Preprocessing Built-in (speckle filter, calibration) Paper-described; code not confirmed public N/A (vector data)
Training No training; pre-fitted RF Paper-described; code availability unclear N/A
Inference Yes - one-call flood map generation Notebook-described N/A
SAR change detection NO - single-image threshold YES - bi-temporal ViT N/A
| DEM integration | NO  | NO  | N/A |
| --------------- | --- | --- | --- |
OSM road accessibility NO NO YES - full graph analysis, isochrones, shortest path
| Flood x OSM overlay      | NO  | NO  | NO (requires user integration)            |
| ------------------------ | --- | --- | ----------------------------------------- |
| Disconnected settlements | NO  | NO  | YES with user implementation              |
| Dashboard                | NO  | NO  | NO (folium/matplotlib visualization only) |
Geographic assumptions Planetary Computer coverage only; no global offline Global S1 GRD pairs Overpass-dependent; offline via .osm.pbf
Hardcoded params RF threshold values; PC API keys required Threshold in ViT head bbox per-call; graph simplification defaults
Evaluation Qualitative only BlackBench / competition Graph metrics via networkx
Reproducibility MEDIUM - API keys required LOW - README 404 HIGH - well-documented stable API
Page 3

Flood Mapping & Geospatial AI | Repository Investigation Report
Attribute Sentinel1-Flood-Finder S1GFlood-Detection (DAM-Net) OSMnx
Key dependencies planetary_computer, pystac_client, rioxarray PyTorch, einops, timm networkx, shapely, geopandas, requests
Hardware CPU (RF model) GPU recommended CPU
Setup difficulty MEDIUM - PC auth needed UNKNOWN LOW
2. Coverage Matrix vs. Hackathon Brief
Component Best Available Coverage Critical Gap
Sentinel-1 SAR flood segmentation Kuro Siwo (multi-temporal, GRD+SLC) No urban coherence by default
Sentinel-2 optical fusion ImpactMesh (S1+S2+DEM fused) Fusion at dataset level; no runtime S2 fetch
Kuro Siwo dataset Kuro Siwo repo itself Generalization to new AOIs needs fine-tuning
Sen1Floods11 benchmark Sen1Floods11 + Prithvi Training code minimal in official repo
SAR change detection ImpactMesh (4-temporal), UrbanSARFloods (coherence) No single end-to-end change detection pipeline exists
Deep learning segmentation Prithvi EO-2.0 / KuroSiwo / ETCI-2021 All chip-based; no tile-stitching for full-scene inference
Infrastructure impact ImpactMesh (Copernicus EMS annotations) No building-level damage report generation
Copernicus DEM terrain analysis ImpactMesh (DEM as 4th modality) No depth estimation or slope analysis module
OSM road accessibility OSMnx No flood-layer integration; must be custom-built
Disconnected settlements OSMnx (graph fragmentation) No automated settlement identification
Geospatial AI dashboard HuggingFace Spaces (Prithvi demo only) No operational emergency-responder dashboard
Grounded incident reporting NONE FOUND Entire component absent from all investigated repos
3. Ranking by Relevance to Hackathon Brief
Rank 1 - IBM/ImpactMesh
Score: 7/7 topic areas partially addressed
• Only repo that simultaneously integrates S1 SAR, S2 optical, Copernicus DEM, multi-temporal change detection, and Copernicus EMS ground truth annotations.
• `pip install impactmesh` works. TerraTorch training config is clean and reproducible.
• Weaknesses: No OSM overlay, no dashboard, no road accessibility, no reporting layer. Created Nov 2025 - very new, low adoption (15 stars), arXiv paper listed as "coming soon" at investigation time.
Rank 2 - Orion-AI-Lab/KuroSiwo
Score: 4/7 topic areas covered
• Highest-quality SAR-only flood segmentation dataset and training code in the field.
• Actively maintained (last push July 2026). MIT license. Pretrained weights downloadable.
Page 4

Flood Mapping & Geospatial AI | Repository Investigation Report
• BlackBench provides a rigorous, standardized evaluation protocol.
• Weaknesses: No optical fusion, no DEM, no infrastructure layer, no dashboard. SAR only.
Rank 3 - NASA-IMPACT/hls-foundation-os (Prithvi EO-2.0)
Score: 3/7 topic areas (optical-centric)
• Best foundation model for Sentinel-2 flood segmentation; strong transfer learning across geographies.
• 407 stars, 97 forks. Apache-2.0. HuggingFace Spaces demo publicly accessible today.
• Weaknesses: No SAR input; 6-band HLS hardcoded; 34 open issues; complex MMSeg environment setup.
Rank 4 - cloudtostreet/Sen1Floods11
Score: 3/7 topic areas
• Canonical benchmark dataset; cited in virtually every competing paper.
• GCS bucket access stable; STAC catalog present for geospatial tooling.
• Weaknesses: No license declared on GitHub; code is notebook-only; last push 2021; 13 open issues with no responses.
Rank 5 - sidgan/ETCI-2021-Competition-on-Flood-Detection
Score: 2/7 topic areas
• Best example of a competition-winning SAR segmentation pipeline with semi-supervised learning.
• Operationally deployed by Orange Business Services - inference achieves 1.22 seconds per 63,000 km² tile.
• Apache-2.0. Documented presentations, poster, and paper available.
• Weaknesses: No multimodal fusion, no terrain, no OSM, no dashboard. Code not updated since June 2022.
Rank 6 - jie666-6/UrbanSARFloods
Score: 2/7 topic areas
• Unique value: SLC coherence for urban flood detection - addresses the hardest SAR scenario (double-bounce cancellation in cities).
• 2024 paper; actively maintained through early 2026.
• Weaknesses: Dataset-only repository; no training code; no license stated.
Rank 7 - gboeing/osmnx
Score: 2/7 topic areas
• The only reliable, production-quality library for OSM road network analysis and graph computations.
• MIT license; excellent documentation; stable API; no setup issues.
• Weaknesses: Not a flood-specific tool; flood overlay and disconnected settlement detection are entirely custom implementation burden.
Page 5

Flood Mapping & Geospatial AI | Repository Investigation Report
Rank 8 - cordmaur/Sentinel1-Flood-Finder
Score: 1/7 topic areas
• Fast, cloud-native Random Forest approach; no GPU required; beginner-friendly.
• Weaknesses: GPL-3.0 copyleft risk; no deep learning; Planetary Computer API lock-in; development slowing since July 2024.
Rank 9 - S1GFlood-Detection (DAM-Net)
Score: 1/7 topic areas
• Interesting bi-temporal ViT architecture with global SAR dataset.
• Weaknesses: README was 404 at investigation time; code availability unconfirmed; do not build dependencies on this.
4. Closest End-to-End Competitors
No public repository implements the complete hackathon brief. The closest approximation
requires assembling multiple repos manually:
ImpactMesh (S1 + S2 + DEM + Copernicus EMS labels)
+ KuroSiwo pretrained weights (SAR backbone)
+ OSMnx (road graph with networkx)
+ Custom integration code:
flood mask GeoJSON --> geopandas spatial join --> edge removal --> connected components
+ Custom dashboard (Streamlit + Folium/MapLibre)
+ Custom grounded reporting (LLM + GeoJSON-to-NL generation)
Academic near-competitors (partial code only):
• *Ambulance STARS* (MDPI 2026): S1 flood detection + OSM routing for ambulance accessibility. No public GitHub repository found.
• *OpenFloodRiskMap (OFRM)*: Web decision support for road flood risk. Appears proprietary/institutional.
• *Copernicus EMS INFLOS*: Operational DEM-based depth estimation. Not open-source.
5. Strongest Reusable Research Baselines
Use Case Recommended Baseline Rationale
SAR backbone weights KuroSiwo pretrained ResNet/UNet on HuggingFace MIT; multi-temporal; globally trained on 43 events
Multimodal training data ImpactMesh-Flood on HuggingFace Apache-2.0; S1+S2+DEM; 200+ flood events
Page 6

Flood Mapping & Geospatial AI | Repository Investigation Report
Use Case Recommended Baseline Rationale
Optical foundation model Prithvi-EO-2.0-300M-TL-Sen1Floods11 Apache-2.0; SOTA on Sen1Floods11; HuggingFace-native
Urban coherence detection UrbanSARFloods dataset via Dataset4EO Unique coherence channel; addresses urban SAR ambiguity
Road network graph engine OSMnx MIT; production-grade; networkx integration
Standard benchmark eval Sen1Floods11 test set + KuroSiwo BlackBench Community standards; enables cross-paper comparison
Semi-supervised training ETCI-2021 pseudo-labeling code Apache-2.0; proven at 63,000 km² scale
6. Component Action Plan
Independently Implementable (no license risk)
• OSM road accessibility + disconnected settlement detection: Build with `osmnx` (MIT) and `geopandas`. Overlay flood mask GeoJSON onto road graph; remove flooded edges; compute
`networkx.connected_components`. No existing repo does this end-to-end - pure custom work estimated at ~2-3 days.
• Copernicus DEM terrain analysis: Use `rasterio` + `richdem` or `pysheds`. DEM tiles freely downloadable from AWS S3 (`s3://copernicus-dem-30m`). No standalone public module exists for this.
• Geospatial dashboard: Streamlit + Folium/Deck.gl. No direct competitor in the open-source space for this specific use case.
• Grounded incident reporting: LLM + structured geospatial output (GeoJSON to natural language narrative). Entirely novel component; no public repo found.
Adapt with Attribution (license permits; citation required)
• SAR flood segmentation model: Use KuroSiwo pretrained weights (MIT). Fine-tune on target AOI with custom data. Cite Bountos et al. 2024 (arXiv:2311.12056).
• Multimodal training pipeline: Fork ImpactMesh (Apache-2.0). Add custom inference entrypoint for new AOI. Cite IBM/DLR/ESA Phi-lab.
• Semi-supervised pseudo-labeling: Adapt ETCI-2021 cyclical pseudo-labeling code (Apache-2.0). Cite Paul and Ganju 2021 (arXiv:2107.08369).
• Foundation model fine-tuning: Use Prithvi-EO-2.0 via TerraTorch (Apache-2.0). Cite IBM NASA 2023 Prithvi paper.
Inspiration Only (license constraints or data restrictions)
• Sen1Floods11 data: No license declared on GitHub - commercial and competition use is legally ambiguous. Use only as an evaluation benchmark. Cite Bonafilia et al. 2020 (CVPRW 2020).
• Sentinel1-Flood-Finder: GPL-3.0 - if the hackathon submission must be Apache or proprietary, GPL is incompatible. Use as architectural reference only.
• UrbanSARFloods: No license. Do not redistribute the dataset or derivatives without explicit author permission.
• DAM-Net (S1GFlood): Code availability unverified (README 404). Do not build a dependency on this.
• Copernicus EMS annotations (via ImpactMesh): Copernicus open license permits research; verify non-commercial restrictions for hackathon prize eligibility before submitting.
7. Missing Components (Must Build From Scratch)
The following components are completely absent from all investigated repositories:
Page 7

Flood Mapping & Geospatial AI | Repository Investigation Report
1. Real-time Sentinel-1 ingestion pipeline - CDSE API or Planetary Computer query for new event acquisitions
2. Automated pre/post-event pair selection - orbit matching, temporal window logic, scene metadata parsing
3. Flood mask to road network overlay - GeoDataFrame spatial join + edge removal from OSM graph
4. Disconnected settlement identification - graph component labeling + settlement polygon lookup from OSM or GHSL
5. DEM-informed flood depth estimation - flood water surface interpolation minus DEM bare-earth elevation
6. Grounded incident reporting - natural language generation from structured geospatial data (LLM-based)
7. Interactive emergency-responder dashboard - real-time map, alert feed, per-settlement accessibility score
8. Full-pipeline evaluation harness - end-to-end F1 at settlement level, not just chip-level pixel accuracy
8. Data Restriction Checklist for Hackathon Submission
Data Source License Hackathon-Safe Notes
Sentinel-1 GRD (ESA Copernicus) Copernicus Open License YES Free for commercial use with attribution
Sentinel-2 L2A (ESA Copernicus) Copernicus Open License YES Same as S1
Copernicus DEM GLO-30 Open (TanDEM-X derived) YES CC Attribution required
OpenStreetMap ODbL YES Share-alike for derived databases; verify if output maps qualify
Kuro Siwo dataset MIT YES Citation required
ImpactMesh dataset Apache-2.0 YES Citation required
Sen1Floods11 dataset UNLICENSED UNCLEAR Contact Cloud to Street before use in competition
UrbanSARFloods dataset UNLICENSED UNCLEAR Contact authors (Jie Zhao, TUM)
Copernicus EMS products Copernicus Open License YES Attribution required
HLS (NASA) data NASA Open Data YES US Government works; public domain
*This report is based on direct repository metadata retrieved via GitHub API, README file contents, commit history, and web research conducted on 2026-10-09. Code that was not publicly accessible (DAM-Net)
has been explicitly flagged. Claims marked as verified were cross-checked against actual file contents or API responses. Claims marked unclear require further verification before relying on them for a competition
submission.*
Page 8
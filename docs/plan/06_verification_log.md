# Verification log — checked on 2026-10-12

These are the facts this plan depends on, each with the source it was checked against. Anything not verified is listed as **open** together with the task that resolves it.

## Verified

| # | Fact | Source | Used in |
|---|---|---|---|
| V1 | CDSE STAC `https://stac.dataspace.copernicus.eu/v1`, collection `sentinel-1-grd`: assets `vv`/`vh` are COG (uint16, nodata 0), plus a `Product` zip and calibration/noise XML; item ids end `_COG`; storage `s3://eodata/...`, endpoint `https://eodata.dataspace.copernicus.eu` | collection JSON (fetched) | P1.1, P1.7 |
| V2 | Queryables include `sat:relative_orbit`, `sat:orbit_state`, `sar:polarizations`, `sar:instrument_mode`, `platform`, `product:type` | `/collections/sentinel-1-grd/queryables` (fetched); CDSE forum | P1.1 |
| V3 | Trishuli bbox 85.2–85.5 E, 28.0–28.3 N, 2026-07-10…09-10: 16 S1D items on tracks 85 ascending (12:21 UTC), 19 descending (00:18 UTC), 121 descending (00:10 UTC), each on a 12-day repeat. First post-event pass: **85A, 2026-08-28T12:21:41Z** | live STAC item search (fetched) | D3, P1.1 tests |
| V4 | Sentinel-1A operations ended 29 June 2026; S1C + S1D restored the 6-day constellation repeat (S1C orbit change 9–23 June 2026) | ESA/CDSE notices ([CDSE orbital reconfiguration](https://dataspace.copernicus.eu/node/3949), [S1C/D final configuration](https://dataspace.copernicus.eu/node/4010), [NOAA OSPO](https://ospo.noaa.gov/data/messages/2026/06/MSG_20260609_1900.html)) | 05 §, limitations |
| V5 | Sentinel Hub S1GRD: `backCoeff` ∈ {BETA0, SIGMA0_ELLIPSOID, GAMMA0_ELLIPSOID, GAMMA0_TERRAIN}; `orthorectify`; `demInstance` ∈ {MAPZEN, COPERNICUS, COPERNICUS_30, COPERNICUS_90}; `speckleFilter` NONE/LEE (window ≤ 7); `resolution` HIGH = 10 m IW; bands VV/VH linear, `localIncidenceAngle`, `shadowMask` (needs RTC), `dataMask`; **no relative-orbit filter** | [docs.sentinel-hub.com S1GRD](https://docs.sentinel-hub.com/api/latest/data/sentinel-1-grd/) | D1, P1.3 |
| V6 | Kuro Siwo SNAP graph: Calibration σ⁰ **linear** (no dB) → Lee Sigma 7×7, target 3×3, σ 0.9 → Terrain-Correction SRTM 1Sec, 10 m, EPSG:3857, bilinear (Land-Sea-Mask also uses SRTM) | `configs/grd_preprocessing.xml` (fetched) | D1, P1.2, P1.7 |
| V7 | Kuro Siwo official split: train 27 / val 7 / test 10 activation ids (in `configs/kuro_siwo_splits.yaml`); channels VV, VH; inputs pre_event_1, pre_event_2, post_event; mean [0.0953, 0.0264]; clamp 0.15; `dem`/`slope` flags effectively false in the default config | `configs/train/data_config.json` (fetched) | P2.1, P2.11 |
| V8 | Kuro Siwo HF GeoTIFFs: 1.02 TB, CC BY 4.0, folders `GRD/` and `SLC/` of numbered `.tar`; GRD sample = flood_vv/vh, sec1_vv/vh, sec2_vv/vh, dem, mask (0/1/2), valid_mask (float32 npy) + info.json. Webdataset repo: 1.96 TB, `train_GRD/`, `test_GRD/` shards | [HF GeoTIFFs](https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-GeoTIFFs), [HF Webdataset](https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-Webdataset) | P2.1 |
| V9 | Kuro Siwo repo: MIT code; README says data CC BY; released FloodViT + SNUNet weights (Dropbox); `main.py --method --backbone --dem --slope` | [GitHub Orion-AI-Lab/KuroSiwo](https://github.com/Orion-AI-Lab/KuroSiwo) | P2.6, ATTRIBUTION |
| V10 | ohsome API v2: base `https://api.heigit.org/ohsome-api/v2-rc`, header `authorization: <key>`, `/extraction/features(.parquet)`, body `aoi`/`filter`/`time`/`clip`; single timestamp = snapshot; GeoParquet output; `properties` removed (all returned). **v1 shuts down 2026-11-30** | [migration guide](https://docs.ohsome.org/ohsome-api/v2-rc/migration_guide.html), [time reference](https://docs.ohsome.org/ohsome-api/v2-rc/reference/time.html), [GeoPandas how-to](https://docs.ohsome.org/ohsome-api/v2-rc/how-to-guides/extraction-geopandas.html) | D2, P3.1 |
| V11 | GLO-30 public bucket `copernicus-dem-30m` (eu-central-1, no account), COG, 1024 px tiles, tile name `Copernicus_DSM_COG_10_<N..>_00_<E...>_00_DEM` (`10` = arc-seconds) | [AWS registry](https://registry.opendata.aws/copernicus-dem/), [bucket readme](https://copernicus-dem-30m.s3.amazonaws.com/readme.html) | P1.5 |
| V12 | pyflwdir signatures: `from_dem(data, nodata=-9999., max_depth=-1., transform, latlon=False, outlets='edge')`; `upstream_area(unit)`; `hand(drain, elevtn)`; `path(idxs|xy, mask, max_length, unit, direction)` | [pyflwdir API reference](https://deltares.github.io/pyflwdir/latest/reference.html) | P1.5, P3.5 |
| V13 | sarsen (alternative local GTC/RTC) is beta; ~25 min per full GRD at 10 m on a 32 GB laptop; output on the DEM grid | [GitHub bopen/sarsen](https://github.com/bopen/sarsen) | why D1 uses Sentinel Hub, not sarsen |
| V14 | EMSR927 activated 26 Aug 2026 for flood extent + damage in Rasuwa; 4 AOIs; ">240 buildings destroyed, 32 damaged" in the Syapru Besi view; cause "reportedly GLOF" (the cause is disputed) | [CEMS news](https://mapping.emergency.copernicus.eu/news/flood-in-nepal-emsr927/), [EU Space image](https://eu-space.europa.eu/components/earth-observation-copernicus/image-of-the-day/copernicus-emergency-management-service-maps-flood-damages-northern-nepal) | P4.6 (check-only) |
| V15 | Event onset ~02:52–02:55 UTC 26 Aug 2026 (seismic); source north flank of Langtang Himal; path Lhende Khola → Bhote Koshi → Trishuli; ~100 km runout | [gee-community-catalog](https://gee-community-catalog.org/projects/nepal_floods_2026/) | D4, P3.5 |
| V16 | A pre-event Sentinel-2 view exists for 24 Aug 2026 (ESA) | [ESA image](https://www.esa.int/ESA_Multimedia/Images/2026/08/Nepal_glacier_collapse_and_flood_24_August_2026) | P1.6 |

## Open (resolve in the named task; record the answer in the task report)

| # | Open question | Resolved in |
|---|---|---|
| O1 | Does the Sentinel Hub Process API count as "raw satellite data" for the PS? | P4.0 organiser Q2 |
| O2 | Exact member layout of Kuro Siwo GRD tars and the info.json event key; total GRD size | P2.1 discovery |
| O3 | Input format of the released SNUNet weights | P2.6 (time box 2 h) |
| O4 | SNAP DEM name for Copernicus 30 m and the parameter names for saving the LIA | P1.7 (`gpt -h`) |
| O5 | ohsome v2 response column names (id, type, validity) | P3.0 |
| O6 | EMSR927 vector layers, legend and image dates | P4.0 (schema only, before FREEZE) |
| O7 | Sentinel Hub free-tier processing-unit quota on CDSE in Oct 2026 | P1.3 (log PU per request) |
| O8 | Whether Sentinel-1C also covers the Trishuli tracks (none seen Jul–Sep 2026) | P1.1 (re-query at run time; the pair selector handles either) |
| O9 | A non-Trishuli 2026 flood AOI with a same-track pre/post pair | P1.8 by T+12 |

## Rejected inputs (PS data rules — disqualification risk)
GEOID-Flood, MMFlood, IBM ImpactMesh (all derived from Copernicus EMS maps); WorldFloods, UrbanSARFloods (not on the PS list); JRC Global Surface Water, ESA WorldCover, GHSL, HRSL (not allowed inputs); Planet/Maxar imagery (not allowed; don't show it either); any OSM edit after 26 Aug 2026; Copernicus EMS / UNOSAT maps (check-only, `eval/` after FREEZE).

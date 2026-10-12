Technical Feasibility and Architectural
Assessment for Space-Based Alpine
Flood and Debris Mapping
Physical Principles and Sensor Trade-Offs in
Mountainous Terrain
Synthetic Aperture Radar versus Optical Spectral Signatures
Spaceborne emergency response in steep alpine environments, such as the Bhote
Koshi-Trishuli corridor in northern Nepal, requires an understanding of how electromagnetic
waves interact with mountain surface cover 1 . Active C-band Synthetic Aperture Radar (SAR),
such as the sensor onboard Sentinel-1 operating at a central frequency of (
), emits microwave signals that penetrate atmospheric cloud cover, monsoonal
rain, and smoke 1 . Sentinel-1 measures both backscatter amplitude ( ) and phase across
dual-polarization channels (VV and VH) at a spatial resolution in Interferometric Wide
(IW) Ground Range Detected (GRD) mode 3 .
Clear standing water acts as a smooth dielectric interface relative to C-band wavelengths,
inducing specular reflection that directs incident microwave pulses away from the radar sensor 3 .
This yields characteristically low backscatter intensity values, typically falling below 3 .
Conversely, mass-movement deposits—including saturated debris, rock avalanches, mudslides,
and scoured gravel channels—exhibit high surface roughness and dielectric variation 3 . These
rough surfaces trigger strong diffuse or volume scattering, raising backscatter intensities to
between and 3 .
Sentinel-2 MultiSpectral Instrument (MSI) optical sensors capture solar radiation reflected from
the Earth's surface across 13 spectral bands spanning the visible, near-infrared (NIR), and
shortwave infrared (SWIR) wavelengths 4 . Optical mapping relies on surface material absorption
and reflectance properties rather than geometry or dielectric constants 3 . The Normalized
Difference Water Index ( ) and Modified
Normalized Difference Water Index (
) isolate open water by exploiting
high green reflectance and strong NIR/SWIR absorption 3 .
Secondary water-quality indices further distinguish hyper-concentrated sediment flows from
clear water 3 . The Normalized Difference Turbidity Index (

 ) and the Normalized Difference
 Chlorophyll Index (   ) measure
 suspended solids and organic material 3  .  While optical  spectral signatures can differentiate turbid
 water, exposed mud, and damaged canopy cover with fine spectral resolution, optical sensors
 are frequently blinded by monsoonal cloud cover during active disaster events  1 .
 Sensor Parameter /   Sentinel-1 SAR (C-Band)   Sentinel-2 MSI (Optical)
 Capability
 Primary Physical   Surface roughness,   Solar reflectance and
|  Interaction  |  structural geometry, and  |  material spectral  |
| ------------- | -------------------------- | ------------------- |
|               |  dielectric properties 3   |  absorption 3       |
 Atmospheric & Night   Full cloud, haze, and   Severe cloud and fog
 Capability   precipitation penetration;   degradation; daytime
|     |  day/night operational  1  |  operational only 1   |
| --- | -------------------------- | --------------------- |
 Spatial Resolution
 (IW GRD   (Visible/NIR),
 spatial sampling)  4
 (Red Edge/SWIR),
 (Atmospheric) 4
 Inundated Clear Water   Low backscatter (   High absorption in
|  Return  |     |  NIR/SWIR; strongly positive  |
| -------- | --- | ----------------------------- |
 ) via
 NDWI/MNDWI 3
 specular reflection  3
 Debris Flow / Mud   Moderate-to-high   High Red/SWIR reflectance;
|  Signature  |  backscatter (  |  elevated NDTI (turbidity)  3  |
| ----------- | --------------- | ------------------------------ |
 ) via rough
 diffuse scattering  3
 Primary Physical Artifacts   Radar shadow, layover,   Cloud obscuration,
|     |  foreshortening, specular  |  topographic shadows,  |
| --- | -------------------------- | ---------------------- |
|     |  wet-mud returns  3        |  atmospheric haze 7    |
 Geometric and Radiometric Normalization Requirements
 Pixel-based change detection across pre-disaster and post-disaster satellite acquisitions
 requires geometric co-registration and radiometric standardization 1  .  Sentinel-1 operates with a
 5 .
 side-looking radar geometry at fixed off-nadir look angles ranging from   to

Comparing acquisitions from different relative orbit tracks (e.g., an ascending track looking
east-northeast versus a descending track looking west-southwest) introduces geometric
parallax 1 . Steep mountain ridges tilt in opposite directions relative to the satellite's line of sight,
creating severe relief displacements ( ) that render two-dimensional spatial
registration mathematically impossible 5 . Automated change detection must therefore restrict
image comparisons strictly to identical Relative Orbit Tracks acquired under matching
geometry 1 .
Radiometric comparability requires Radiometric Terrain Flattening (RTC) 1 . Standard radar
backscatter metrics ( ) assume a flat ground surface, causing steep terrain slopes facing the
radar sensor to appear artificially bright due to a larger local contributing ground area per range
cell 3 . Converting Ground Range Detected (GRD) intensity values to gamma-nought radiometric
terrain-flattened backscatter ( ) corrects for local illuminated area variations using a
high-resolution Digital Elevation Model (such as the Copernicus WorldDEM-30) 1 . Thermal noise
removal must also be applied to eliminate instrument noise in cross-polarization (VH) channels
at low signal levels, ensuring that temporal changes reflect physical ground alterations rather
than orbital or processing artifacts 3 .
Topographic and Environmental Artifacts in Alpine Corridors
High-relief alpine environments introduce physical distortion mechanisms that systematically
degrade conventional machine learning classifiers:
● Radar Shadow and Layover : When mountain slopes face away from the radar look
direction at angles steeper than the sensor's look angle, no microwave energy reaches
the ground, creating radar shadow 3 . Shadowed pixels record only instrument noise,
displaying low backscatter values ( ) that match the specular reflection
of open water 3 . This produces widespread false-positive flood detections along steep
north-facing slopes. Conversely, layover occurs on steep slopes facing the sensor, where
the radar wavefront strikes the mountain peak before the base, mapping mountain tops
onto valley floors and corrupting spatial boundaries 5 .
● Vegetation Canopy Scattering : Dense forest canopies induce volume scattering 3 .
Monsoonal rainfall increases canopy water content and changes dielectric constants,
elevating backscatter returns by to . This canopy noise can obscure
sub-canopy inundation or mimic ground-level debris accumulation 3 .
● Specular Reflection from Saturated Mud : High-velocity debris flows leave smooth
deposits of fine, saturated silt along valley floors. These wet, fine-grained mud surfaces
undergo specular reflection, generating low backscatter signatures identical to standing
water 3 . Consequently, single-date SAR backscatter intensity alone cannot differentiate
standing water from smooth mud deposits without integrating elevation priors or temporal
optical data 3 .
● Speckle Noise : Coherent wave interference produces multiplicative speckle noise,

causing granular intensity fluctuations across homogeneous targets 9 . Speckle corrupts
pixel-level neural feature extractors unless suppressed using spatio-temporal filtering
(such as Refined Lee or multitemporal stack filtering) 9 .
● Mixed Pixel Contamination : Narrow Himalayan river channels ( to wide)
frequently span multiple land-cover classes within a single pixel grid 4 . These
mixed pixels combine turbid water, exposed bedrock, destroyed vegetation, and road
remnants, blurring class boundaries and causing edge classification dropouts 4 .
● Acquisition Timing Latency : Sentinel-1 operates on a 12-day single-satellite repeat
cycle (or 6 days when a constellation pair is active) 1 . Because high-altitude glacier
collapses, landslide dam bursts, and flash floods evolve over minutes to hours, satellite
passes rarely coincide with peak discharge 1 . Imagery captured days after an event often
records receding water levels, dried mud crusts, or re-established channels rather than
peak inundation, leading to underestimation of maximum hazard extents 3 .
Task Formulation and Training Data Compatibility
Audit
Disambiguating Inundation, Debris Flow, and Infrastructure Damage
Accurate post-disaster mapping requires distinguishing between three distinct physical hazards,
each characterized by unique scattering mechanisms and spectral profiles:
Inundation mapping delineates open, standing, or slow-moving water 1 . Its primary physical
indicator is a drop in SAR backscatter intensity ( ) caused by specular
reflection, paired with high optical NDWI and MNDWI values 3 .
Debris and sediment detection identifies rockslides, ice-mud avalanches, and sediment deposits
along valley floors 5 . In SAR imagery, coarse rock deposition increases micro-relief roughness,
causing backscatter increases ( to ) relative to pre-event
baselines 3 . In optical imagery, debris flows strip away vegetation, replacing high near-infrared
returns with high red/SWIR reflectance and elevated NDTI turbidity values 3 .
Infrastructure damage classification detects structural destruction across roads, bridges, and
settlements 1 . Built structures act as corner reflectors that generate strong double-bounce
backscatter in pre-event SAR imagery 5 . Severe structural damage eliminates double-bounce
geometry, causing localized backscatter drops or InSAR coherence decorrelation 5 . Because
individual buildings and road segments are narrow relative to satellite pixels, direct
pixel-level semantic segmentation of infrastructure damage is prone to high error rates 4 .
Reliable damage assessment requires intersecting high-confidence hazard spatial masks (flood
and debris) with pre-existing vector infrastructure networks 1 .
Audit of KuroSiwo and Sen1Floods11 Datasets
Applying public deep learning benchmarks to high-relief Himalayan disaster events introduces

 domain shift that can compromise model performance  1 .
 Evaluation   KuroSiwo Dataset   Sen1Floods11   Target Himalayan
|  Parameter  |     |  Dataset  |  Domain  |
| ----------- | --- | --------- | -------- |
 Primary Focus   Multi-temporal SAR   Global Sentinel-1   Compound flood,
|     |  flood mapping 9   |  flood mapping 4   |  debris, and  |
| --- | ------------------ | ------------------ | ------------- |
 settlement isolation  1
 Topographic   Lowland plains,   Flat agricultural   Extreme alpine
 Representation   coastal deltas, river   plains, lowland river   relief, steep
|     |  basins  9  |  basins  4  |  V-shaped valleys 1   |
| --- | ----------- | ----------- | --------------------- |
 Target Physical   Open-water   Open-water   High-velocity debris
|  Process  |                |                |  flows, mud  |
| --------- | -------------- | -------------- | ------------ |
|           |  inundation (  |  inundation (  |              |
 deposits, flooding 5
|     |  drops) 3   |  drops) 3   |     |
| --- | ----------- | ----------- | --- |
 Label Noise &   Low noise; expert   High noise in weak   Mixed signal
|  Verification  |  manual           |  split; auto JRC  |  signatures,  |
| -------------- | ----------------- | ----------------- | ------------- |
|                |  annotations  11  |  thresholded  4   |  topographic  |
 shadows 3
 Himalayan   Poor for debris;   Poor; weak labels   Requires
 Generalization   susceptible to   corrupt terrain   topographic
|     |  shadow noise  3  |  features  3  |     |
| --- | ----------------- | ------------- | --- |
 normalization and
 domain adaptation 1
 The KuroSiwo dataset contains global multi-temporal Sentinel-1 SAR imagery (GRD and Single
 Look Complex patches) with expert manual annotations  9 .   Although KuroSiwo provides high
 label accuracy, its geographical sampling heavily favors lowland floodplains, coastal wetlands,
 and broad river valleys 9  .  It models water almost exclusively  as a specular reflection surface (
 drops)  3 .  It lacks explicit classes for high-velocity  alpine rock-ice avalanches, sediment-laden
 mudflows, or mountain channel scouring where radar backscatter increases  3 .  Models trained
 solely on KuroSiwo fail to detect high-roughness debris deposits, misclassifying them as
 unaffected land.
 The Sen1Floods11 dataset includes Sentinel-1 and Sentinel-2 chips across 11 global flood
 events 4   . Its weakly supervised training split was  generated automatically by thresholding
 historical Joint Research Centre (JRC) Permanent Water layers and Sentinel-1 backscatter  4 .  In
 steep mountain terrain, radar shadows and cloud cover artifacts contaminate these weakly
 supervised labels with false-positive water annotations 3  .   Furthermore, its hand-labeled test set
 contains very few alpine scenes, making it insufficient for training models on mountain hazard

cascades 4 .
Public training benchmarks model flooding as a planar water-extent task over gentle terrain 4 .
Himalayan events, such as the Trishuli or Chamoli disasters, represent dynamic hazard
cascades involving rock avalanches, mud deposition, and channel blockages 5 . Deploying
models trained on KuroSiwo or Sen1Floods11 without domain adaptation results in false
negatives along debris tracks and false positives in radar shadow zones 3 .
Zero-Leakage Evaluation Protocol for Alpine Corridors
Evaluating model generalization to unseen Himalayan scenes requires strict isolation between
training, validation, and test splits 1 .
Random patch-based or tile-based splits across the same satellite image introduce severe
spatial autocorrelation 1 . Adjacent pixel patches share structural terrain features,
atmospheric conditions, and speckle noise, leading to artificially inflated evaluation scores. To
prevent spatial leakage, data splitting must enforce a Geographic Catchment Isolation Protocol 1 .
The training split must be assembled from geographically distinct river basins (such as the
Marsyangdi, Seti River, or historical 2021 Chamoli catchments) 5 . The evaluation set must
consist of completely disjoint river corridors (such as the Trishuli-Bhote Koshi corridor)
separated by a spatial buffer exceeding 1 .
Models must not access pre-event imagery or orbit tracks from the evaluation catchment during
training 1 . Relative Orbit Tracks assigned to the validation set must be completely excluded from
training splits to prevent neural networks from memorizing static, terrain-induced backscatter
patterns or specific shadow geometries 5 .
Dataset normalization statistics (mean, standard deviation, feature scaling) must be computed
strictly on the training split 1 . Elevation-derived features (such as slope, aspect, and HAND) must
be generated independently per catchment to prevent global spatial statistics from leaking
across splits 1 .
Spatial Block Cross-Validation must partition training and validation folds across major
Himalayan river basins:
● Fold 1 : Training on the Western Himalaya (Annapurna/Gandaki basins); Validation on the
Central Himalaya (Chamoli/Alaknanda basins) 5 .
● Fold 2 : Training on the Central Himalaya (Karnali/Seti basins); Validation on the
Marsyangdi basin.
● Fold 3 : Training on the Eastern Himalaya (Tamur/Arun basins); Validation on the
Trishuli-Bhote Koshi corridor 1 .
Multimodal Data Fusion and Network Graph Analytics
Hydro-DEM Topographic Filtering
Raw semantic segmentation predictions from satellite classifiers often contain false positives,
such as predicted water bodies on steep mountain ridges or isolated flood pixels in high-altitude
canopy cover. Incorporating elevation data provides physical constraints that eliminate these

non-physical predictions 1 .
Using the Copernicus WorldDEM-30 ( spatial resolution), three hydrologically relevant
spatial rasters are computed 1 :
● Slope Map ( ) : Local topographic gradient derived via spatial elevation derivatives:
● Height Above Nearest Drainage (HAND) : Normalizes terrain elevation relative to the
local drainage network along hydraulic flow paths 10 . For every pixel, HAND measures the
vertical distance to the nearest stream channel cell determined by flow accumulation
lines.
● Flow Accumulation : Calculates the upstream contributing area per cell using
deterministic 8-direction (D8) flow routing algorithms.
Physically constrained rules refine the classifier predictions:
● Inundation Spatial Rule : Standing water cannot persist on steep slopes or elevated
terrain 10 . Pixels classified as flooded are masked out as false positives if or if
, unless confirmed as an established glacial lake.
● Debris Flow Spatial Rule : Debris deposits concentrate along valley floors and channel
corridors 5 . Candidate debris predictions are validated only if they lie within low HAND
zones ( ) or along high flow-accumulation channels downslope from
identified slope failures 5 .
Vector Network Graph Topology and Isolation Analysis
To identify cut-off settlements, the system builds a road network graph from
OpenStreetMap (OSM) snapshots acquired prior to the event date 1 .
Graph construction proceeds as follows:
● Graph Nodes ( ) : Represent road intersections, bridge structures, village settlements,
district towns, and regional medical facilities 1 .
● Graph Edges ( ) : Represent road segments connecting nodes, weighted by physical
length and nominal travel time 13 .
AI-derived flood and debris spatial masks are converted into spatial vector polygons 1 .
Spatial intersection queries identify damaged infrastructure segments:

 . Edge traversal weights are
 updated dynamically:
 Let   represent populated village nodes, and   represent  functional emergency
 facilities (such as district hospitals or relief centers)  1 .   For every settlement   , pathfinding
 algorithms (such as Dijkstra or A*) compute post-disaster reachability to the nearest accessible
|  medical facility  |  :  |     |     |
| ------------------ | --- | --- | --- |
 A settlement   is flagged as  Cut-Off  if   , indicating  complete network
 disconnectivity 1  .
 System Architecture and Operational Pipeline
 End-to-End Operational Pipeline Specifications
 The automated processing system ingests raw satellite imagery and elevation models,
 executing multi-stage feature extraction, topological filtering, graph analytics, uncertainty
 quantification, and report generation 1  .
|  Pipeline Module  |  Input Data  |  Processing        |  Output Data /  |
| ----------------- | ------------ | ------------------ | --------------- |
|                   |              |  Algorithm / Core  |  Artefact       |
 Framework
 1. Data Ingestion &   Raw Sentinel-1   SNAP/GDAL   Co-registered,
 Preprocessing   GRD, Sentinel-2   processing: Doppler   radiometrically
|     |  L2A, Copernicus  |  geocoding,  |  calibrated image  |
| --- | ----------------- | ------------ | ------------------ |
|     |  DEM  1           |  Same-Orbit  |                    |
 stacks (
 grid) 1
 Alignment,
 flattening, Sen2Cor
 cloud masking 1

 2. Multimodal   Pre/Post S1 & S2   Dual-Stream   Softmax class
 Neural   image stacks, DEM   ResNet/Swin   probability maps:
|  Segmentation  |  slope/aspect  1  |  Transformer  |     |
| -------------- | ----------------- | ------------- | --- |
 ,
 backbone with
 Temporal Difference   ,
 Attention
 Cross-Fusion 1 1
 3. Hydro-DEM   Softmax maps,   D8 hydrologic   Refined binary and
 Filtering   Copernicus DEM   routing, HAND   multi-class vector
|     |  (30m) 1   |  raster generation,  |  hazard masks (  |
| --- | ---------- | -------------------- | ---------------- |
 slope thresholding (
 )  1
 )  10
|  4. Topological  |     |  NetworkX/PostGIS  |  Damaged  |
| ---------------- | --- | ------------------ | --------- |
 , Pre-event
|  Graph Engine  |     |  spatial intersection,  |  road/bridge  |
| -------------- | --- | ----------------------- | ------------- |
 OSM Snapshot
|     |     |  edge deletion,  |  segments, list of  |
| --- | --- | ---------------- | ------------------- |
 (ohsome API) 1
|     |     |  Dijkstra reachability  |  isolated village  |
| --- | --- | ----------------------- | ------------------ |
 pathfinding 1 3
 nodes
 [cite: 1, 2]
 5. Conformal   Softmax probability   Class-Conditional   Spatial uncertainty
 Uncertainty   maps, Calibration   Conformalized Risk   heatmaps,
|  Quantification  |     |  Control (CRC) 1 6  |  coverage-guarantee  |
| ---------------- | --- | ------------------- | -------------------- |
 Set
 d prediction sets
 [cite: 15, 16]
 [cite: 15, 16]
|  6. Grounded  |     |  Deterministic JSON  |  Structured JSON  |
| ------------- | --- | -------------------- | ----------------- |
 , damaged
|  Copilot Engine  |     |  context aggregation  |  summary, bilingual  |
| ---------------- | --- | --------------------- | -------------------- |
 infrastructure
|     |     |  + Large Language  |  situation report  |
| --- | --- | ------------------ | ------------------ |
 vectors, UQ
|     |     |  Model constrained  |  (English & Nepali)  1  |
| --- | --- | ------------------- | ----------------------- |
 metrics  1
 by strict schema  1
 Situation-Report Copilot and Grounded Generation
 The Situation-Report Copilot converts spatial graph metrics into concise situation reports for
 emergency managers 1  .  To prevent hallucinated numbers  or unverified claims, text generation is
 strictly decoupled from spatial metric calculations  1 :
 Spatial analysis engines compute all quantitative metrics (such as flooded surface area in
 , length of damaged roads in   , count of damaged bridges,  and exact names of isolated

villages) using deterministic spatial queries 1 . These values are assembled into a structured
JSON payload.
The Large Language Model receives this JSON payload alongside system prompts that strictly
forbid generating any number, location name, or casualty figure not present in the input context 1 .
System prompts enforce bilingual text generation in both English and Nepali 1 . Nepali language
output uses standardized disaster management terminology approved by the Nepal National
Disaster Risk Reduction and Management Authority (NDRRMA) 1 .
Uncertainty Quantification and Anti-Hallucination
Controls
Conformal Prediction for Risk-Controlled Semantic Segmentation
To prevent unverified hazard claims from misleading rescue teams, the neural network must
output statistical uncertainty bounds alongside classification predictions 15 . Standard softmax
outputs are often overconfident and do not provide statistical guarantees 1 5 . The system
implements Split Conformal Prediction (CP) and Conformalized Risk Control (CRC) to generate
prediction sets with user-defined coverage guarantees 15 .
Let represent the input satellite image stack, and
represent the true ground-truth segmentation mask across
classes (where , , and ) 16 . The neural
network outputs estimated class probability vectors for each pixel
position 16 .
A calibration dataset , independent of training and testing sets, is
evaluated 1 6 . For each pixel, a non-conformity score measures prediction error 16 :
To control false negatives in disaster detection, Class-Conditional Conformal Prediction (CCCP)
derives separate quantile thresholds for each class 17 . Given a
user-defined risk tolerance (such as , corresponding to a
statistical coverage guarantee) 15 , the class conformal threshold is calculated as the
empirical quantile of the non-conformity scores computed over calibration

pixels belonging to class 17 .
For a new test pixel at position , the system constructs a Prediction Set
16 :
Under data exchangeability, the prediction set satisfies the marginal coverage
guarantee 1 6 :
Practical Interpretation of Prediction Sets
The size (cardinality) of the prediction set directly reflects predictive uncertainty 16 :
● Singular Prediction Set ( ) : High model confidence. If
, the pixel is confidently classified as open water 1 6 .
● Multi-Label Prediction Set ( ) : High prediction ambiguity. If
, the physical signature at that location is ambiguous
(such as wet mud or shallow turbulent flow) 1 6 .
● Empty Prediction Set ( ) : Out-of-distribution input anomaly (such as
corrupt pixel values or extreme noise).
In the response dashboard, multi-label prediction sets are displayed as spatial uncertainty
heatmaps. Regions of high ambiguity are highlighted, signaling to operational personnel that
satellite-derived predictions in these zones require manual confirmation prior to dispatching
emergency resources 1 6 .
Evaluation Methodology Against Official Reference
Maps
Evaluating system performance against official Copernicus Emergency Management Service
(CEMS) reference maps (activation EMSR927 for the Trishuli flood event) requires a
reproducible, zero-leakage benchmarking protocol 1 .
Official CEMS vector polygons, UNOSAT damage maps, and post-event OSM edits are strictly

 excluded from model input, feature engineering, and inference pipelines  1  . These layers are
 ingested solely as ground-truth evaluation targets 1  .
 CEMS EMSR927 vector layers delineating flood extents, mudslides, and damaged structures
 are rasterized onto a   spatial grid matching the  model's output tensor, aligned to the
 EPSG:32645 (UTM Zone 45N) coordinate reference system.
 Evaluation Metric   Mathematical Formulation   Target Domain Focus
|  Class Intersection over  |     |  Evaluated independently for  |     |
| ------------------------- | --- | ----------------------------- | --- |
 Flood and Debris classes 1 4
 Union (   )
 Boundary F1-Score (
 Evaluated within a
|  )  |     |  buffer along vector hazard  |     |
| --- | --- | ---------------------------- | --- |
 perimeters
|  Isolated Village Precision  |     |  Compares predicted cut-off   |     |
| ---------------------------- | --- | ----------------------------- | --- |
|  / Recall                    |     |  nodes against official CEMS  |     |
 maps  1
 Architectural Alternatives, Failure Modes, and
 Falsification Framework
 Comparative Analysis of Architectural Alternatives
|  Modeling  |  Core Algorithmic  |  Key Technical  |  Critical         |
| ---------- | ------------------ | --------------- | ----------------- |
|  Paradigm  |  Mechanism         |  Strengths      |  Vulnerabilities  |
 Proposed:   Fusion of S1 SAR,   High accuracy;   Requires GPU
 Dual-Stream   S2 Optical, and   distinguishes open   infrastructure;
 Multimodal   DEM rasters using   water from debris   vulnerable to
 Transformer   Swin Transformer   flows  9   domain shift if
|     |  backbones  1  |     |  uncalibrated 4   |
| --- | -------------- | --- | ----------------- |
 Alternative A:   Automatic   Computationally   High false-negative
|  Classical  |  backscatter  |  efficient;  |  rate on rough  |
| ----------- | ------------- | ------------ | --------------- |
 HAND-Otsu   thresholding (Otsu)   deterministic;   debris; fails in radar
 Thresholding   masked by HAND   requires no deep   shadow 3
|     |  rasters 1 0  |  learning 7   |     |
| --- | ------------- | ------------- | --- |

Alternative B: Interferometric Detects ground Severe temporal
InSAR Coherence phase coherence disruption at decorrelation over
Change Detection correlation from sub-pixel scales 5 vegetation and
complex S1 SLC snow 5
pairs 5
Alternative C: Pre-trained Satellite High data efficiency; High computational
Foundation Model Image Time Series robust zero-shot footprint; spatial
Fine-Tuning models (e.g., TiMo, feature sampling fixed at
Prithvi-EO-2.0) 1 4 representations 9
Critical Failure Modes and Limitations
● False Positives from Topographic Shadowing : In steep, north-facing slopes, radar
shadows attenuate backscatter down to the noise floor, triggering false positive water
detections 3 . Mitigation : Mask all pixels where local incident angles satisfy or
where terrain shadow geometries projected from the Copernicus DEM intersect the
line-of-sight vector 1 .
● False Negatives from Smooth Wet Mud Deposits : Saturated silt deposits along
riverbeds induce specular reflection, causing models to misclassify debris tracks as
standing water 3 . Mitigation : Incorporate optical SWIR ratios and NDTI indices when
clear-sky Sentinel-2 data is available; apply HAND slope rules ( ) to
disallow standing water on sloped channels 3 .
● Sub-Pixel Channel Scouring and Resolution Loss : Torrent channels narrower than
blend with surrounding bank vegetation within a single pixel cell,
leading to omission of narrow flood paths 4 . Mitigation : Apply spatial super-resolution
processing along OSM stream vectors prior to classification.
● Graph Routing Errors from Incomplete Vector Maps : Remote Himalayan valleys often
contain unmapped trails or missing bridges in pre-event OpenStreetMap snapshots 1 . If a
critical connecting segment is missing from the input graph, pathfinding algorithms will
incorrectly flag reachable villages as isolated 1 . Mitigation : Ingest settlement density layers
(such as the High-Resolution Settlement Layer) and run road-extraction overlays on
pre-event optical imagery to repair network gaps prior to graph analysis.
Experimental Framework for Assumption Falsification
Four empirical experiments test and validate the core assumptions of this architecture:
Experiment 1: Testing Cross-Track Change Detection Performance
● Hypothesis : Pixel-based change detection across mixed ascending and descending orbit
tracks produces elevated false-positive rates due to terrain relief displacement 1 .
● Setup : Run the change detection pipeline on the Trishuli corridor using an ascending
pre-event Sentinel-1 image (Track 56) paired with a descending post-event Sentinel-1

image (Track 63) 5 . Compare results against a control setup using matching orbit tracks
(Track 56 pre- and post-event) 1 .
● Falsification Metric : If the cross-track False Positive Rate ( ) exceeds the
same-track by more than over non-flooded steep terrain ( ),
the assumption that cross-track images can be used for change detection is empirically
falsified.
Experiment 2: Evaluating All-Weather SAR Autonomous Mapping
● Hypothesis : Sentinel-1 SAR imagery alone, without optical Sentinel-2 confirmation, is
sufficient to map complex alpine debris flows 1 .
● Setup : Mask out post-event Sentinel-2 optical bands, forcing the network to segment
debris flows using only dual-polarized Sentinel-1 SAR intensity and DEM rasters 1 .
Evaluate mIoU against the complete multimodal pipeline (SAR + Optical + DEM) across
the EMSR927 Trishuli validation area 1 .
● Falsification Metric : If the SAR-only Debris Class IoU drops by more than relative
to the multimodal pipeline, the assumption of SAR self-sufficiency for debris mapping is
falsified, proving optical data is necessary for resolving mud and rock deposits.
Experiment 3: Evaluating Weakly Supervised Pre-Training Benefits
● Hypothesis : Pre-training semantic segmentation backbones on global weakly supervised
datasets (such as Sen1Floods11) improves generalization to Himalayan flood events
compared to training from scratch 4 .
● Setup : Train two identical network architectures: Model A initialized with weights
pre-trained on Sen1Floods11 weakly supervised chips, and Model B initialized with
ImageNet weights 4 . Fine-tune both models on a small set of manually annotated
Himalayan scenes (e.g., Chamoli 2021) and evaluate on the unseen Trishuli 2026
dataset 1 .
● Falsification Metric : If Model A fails to achieve a statistically significant improvement (
) in mIoU over Model B, the utility of lowland weakly supervised pre-training
for alpine flood mapping is falsified.
Experiment 4: Assessing Conformal Guarantees Under Domain Shift
● Hypothesis : Conformal prediction prediction sets maintain their statistical
coverage guarantee ( ) when deployed across distant Himalayan catchments
without local recalibration 1 5 .
● Setup : Calibrate conformal quantile thresholds using a calibration set drawn
from European flood scenes (KuroSiwo) 9 . Apply these fixed thresholds to generate
prediction sets over the unseen Trishuli test scene 1 . Compute the true empirical

coverage rate 16 .
● Falsification Metric : If the empirical coverage rate over the Trishuli test set falls below
(below coverage for ), the assumption of
domain-invariant conformal validity is falsified, proving that local alpine calibration sets are
mandatory 1 6 .
Nuanced Operational Recommendations
Operational deployment of space-based disaster mapping models in alpine terrain requires
balancing satellite physical limits with user safety requirements 1 .
First, because Sentinel satellites operate on multi-day repeat orbits, spaceborne systems
cannot provide real-time early warnings for sudden glacier collapses minutes before impact 1 .
Satellite mapping serves primarily as a post-event rapid damage assessment and routing tool 1 .
Second, automated change detection pipelines must strictly enforce identical Relative Orbit
Tracks and apply Radiometric Terrain Flattening ( ) to prevent terrain artifacts from
corrupting hazard maps 1 .
Third, language model copilots must be strictly constrained by deterministic spatial data
payloads, preventing unverified numbers or casualty claims from entering emergency situation
reports 1 .
Finally, integrating Conformal Prediction heatmaps ensures that first responders receive
transparent statistical confidence bounds alongside hazard extent maps, enabling safer and
more informed emergency routing in complex mountain terrain 15 .
Works cited
1. Track B.pdf
2. Space Track.pdf
3. Chamoli disaster: pronounced changes in water quality and flood,
https://pmc.ncbi.nlm.nih.gov/articles/PMC8381862/
4. Sen1Floods11: A Georeferenced Dataset to Train and Test Deep,
https://openaccess.thecvf.com/content_CVPRW_2020/papers/w11/Bonafilia_Sen1
Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPR
W_2020_paper.pdf
5. Pre-collapse motion of the February 2021 Chamoli rock ... - NHESS,
https://nhess.copernicus.org/articles/22/3309/2022/
6. Changes in the flood plains and water quality along the Himalayan,
https://www.research.unipd.it/retrieve/b48b8ab4-2d7f-4efb-9f2d-28ba1cbeb181/Ch
anges%20in%20the%20flood%20plains%20and%20water%20quality%20along%
20the%20Himalayan%20rivers%20after%20the%20Chamoli%20disaster%20of%
207%20February%202021_compressed.pdf
7. Mapping of flood areas using Sentinel-1 synthetic aperture radar,
https://www.researchgate.net/publication/356791105_Mapping_of_flood_areas_us

ing_Sentinel-1_synthetic_aperture_radar_SAR_images_with_Google_Earth_Engi
ne_cloud_platform_-A_case_study_of_Chamoli_district_Uttarakhand-India
8. Pre-collapse motion of the February 2021 Chamoli rock ... - NHESS,
https://nhess.copernicus.org/preprints/nhess-2021-333/nhess-2021-333.pdf
9. Kuro Siwo: 33 billion $m^2$ under the water. A global multi,
https://www.researchgate.net/publication/397201321_Kuro_Siwo_33_billion_m2_u
nder_the_water_A_global_multi-temporal_satellite_dataset_for_rapid_flood_mapp
ing
10. Water Resources Management in Dehradun Using GIS & Remote,
https://spaceborne.in/water-resources-management-in-dehradun-using-gis-remote
-sensing-space-borne/
11. GitHub - Orion-AI-Lab/KuroSiwo: Code and data for Kuro Siwo flood,
https://github.com/Orion-AI-Lab/KuroSiwo
12. Datasets Benchmarks 2024 - NeurIPS 2026,
https://neurips.cc/virtual/2024/events/datasets-benchmarks-2024
13. Multi-Temporal Satellite Observations and Machine Learning-Based,
https://www.mdpi.com/2072-4292/18/18/3204
14. Spatiotemporal Foundation Model for Satellite Image Time Series,
https://arxiv.org/html/2505.08723v1
15. Conformal Semantic Image Segmentation: Post-hoc Quantification,
https://arxiv.org/html/2405.05145v1
16. Conformal Semantic Image Segmentation: Post-hoc Quantification,
https://openaccess.thecvf.com/content/CVPR2024W/SAIAD/papers/Mossina_Con
formal_Semantic_Image_Segmentation_Post-hoc_Quantification_of_Predictive_U
ncertainty_CVPRW_2024_paper.pdf
17. SACP: Spatially-Adaptive Conformal Prediction in Uncertainty,
https://openreview.net/pdf/6d7b64fa249cf803fc5119abe5487b3fe5eb190b.pdf
18. ConformalSAM - AMiner,
https://cz5waila03cyo0tux1owpyofgoryroob.aminer.cn/D5/35/84/D535840D160131
B274E6323F010CE6F2.pdf
19. Uncertainty quantification for LiDAR-based maps of ditches and,
https://research.slu.se/files/19145912/fulltext.pdf
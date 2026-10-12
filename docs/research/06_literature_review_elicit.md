Satellite-based flood, debris and accessibility mapping for disaster response

Evidence synthesis

The literature supports a practical pipeline—map water and observable damage from satellite data, translate mapped
impacts into network disruption, then expose uncertainty and provenance to decision-makers—but it does not
support treating these as one already-solved end-to-end task. Flood segmentation has public benchmarks and
reproducible baselines, while event-independent evaluation, verified infrastructure damage labels and image-to-
accessibility integration remain less established.[1][2][3] The matrix accompanying this brief curates 19 papers span-
ning benchmark, method, infrastructure and operational-accessibility evidence.

1. Sentinel-1 SAR flood segmentation and change detection

The most useful early shared baseline is Sen1Floods11: 4,831 georeferenced 512×512 chips spanning 11 flood events,
six continents, and multiple biomes/ecoregions. Its original FCNN comparisons show that flood-specific labels matter,
and that event-derived optical labels can scale training beyond scarce hand labels; backscatter thresholding remains
a useful simple comparator, especially for permanent water. The dataset and training/evaluation code are public.[1]

A stronger operational comparison evaluates AlbuNet-34, FCN, DeepLabV3+, U-Net and U-Net++ against a rule-
based Sentinel-1 processor. Dual-polarization inputs improved IoU by five percentage points relative to the rule-
based chain, a weighted cross-entropy/Lovász combination added two points, and radiometric augmentation helped
whereas geometric augmentation hurt. Two flood-event tests reached IoU 0.96 and 0.94; these results should not be
compared naively with other papers’ benchmark IoUs because event, label, water-class and split definitions differ.[4]

For a student baseline, compare thresholding (or an operational processor, if available), Random Forest, and a U-Net
on Sentinel-1 VV/VH, and report per-event precision, recall, F1 and IoU. Dual-polarization and event-level testing
are represented in existing benchmarks.[4] Include permanent-water exclusion and a pre-event reference where
available; pixel-level random splits do not establish transfer.

2. Multitemporal SAR and optical fusion

Fusion has a clear physical rationale: SAR is available through cloud and darkness, while optical reflectance can help
distinguish water classes and land-cover context. On Sen1Flood11, a Sentinel-1/Sentinel-2 deep-learning study used
focal loss and reported test IoU 52.30%, mIoU 52.99%, and overall accuracy 92.81%; its Bolivia evaluation had IoU
76.74% and mIoU 47.88%. The spread across metrics and test subsets illustrates why class definition and split details
must accompany headline scores.[5]

A temporally dense Sentinel-1/Sentinel-2/DEM case study of the 2018 Baige outburst flood in Tibet used index
thresholds in cloud-free areas and SAR features plus terrain in cloudy areas, with a Random Forest prediction stage.
Field/confusion-matrix validation reported 92.3% overall accuracy and Kappa 0.89, and the full event extent was pro-
duced within five days. This is valuable mountainous-event evidence, but it is a single case rather than a cross-region
generalization test.[6]

GEOID-Flood, reported in 2026, is a promising newer benchmark: more than 14,000 tiles from 219 events in 65
countries, with co-registered pre/post Sentinel-1, pre-event Sentinel-2 and DEM, and manually validated labels. Its
abstract reports modest but consistent foundation-model advantages, best transient-water resolution from finetuned
SAR-optical fusion, and improved unseen-event transfer relative to earlier datasets. Exact split definitions and nu-
meric metrics were not verified in the available record, so those claims should be checked against the full paper
before operational reliance.[7]

3. Flood and debris in mountainous terrain

Mountain terrain raises distinct failure modes: layover/shadow, steep-slope drainage, vegetation, roughness changes,
and rapidly changing debris or outburst water. The Baige case above shows a workable Sentinel-1/2/DEM collabo-
ration strategy. Earlier debris-hazard work fused RADARSAT-1 SAR with SPOT-5 optical/3D mapping for Taiwan
slope failures and compared delineation/volume estimates with field measurements, but the retrieved abstract gives
no numerical accuracy.[6][8]

1

The retrieved SAR landslide/debris studies are individual-event demonstrations: the Baige outburst flood is one
mountainous case, while the Taiwan debris-hazard study compares fusion outputs with local ground truth.[6][8]
This evidence supports terrain context as a testable input, not a claim that one architecture is established as superior.

4. Transfer learning and generalization to unseen events

Randomly held-out tiles from the same event are a weak proxy for deployment. Geographic location, incidence
angle, land cover, flood dynamics and label sources shift the input and target distributions. A Sen1Floods11 domain-
generalization study treating flood events as separate source domains reports about a 3% IoU/F1 gain.[9]

UrbanSARFloods adds 8,879 512×512 chips from 18 events across five continents, with Sentinel-1 intensity and co-
herence. Its abstract emphasizes persistent urban-water difficulty and says weighted cross-entropy and pretrained
transfer learning do not by themselves resolve class imbalance and limited training data.[10] GEOID-Flood’s event
diversity and reported unseen-event transfer are promising, but should be independently checked using explicit
leave-one-event-out or leave-one-region-out splits.[7]

5. Road, bridge and building damage estimation

Damage evidence spans markedly different sensors and spatial scales. A 2024 tiered bridge study combines Sentinel-
1 coherence difference, crowdsourced information and high-resolution imagery with semantic segmentation, and
validates a case containing 17 bridges in Ukraine.
It demonstrates a multiscale assessment design, but is not a
validated satellite-only classifier for flood-damaged bridges.[2]

A post-disaster road-accessibility framework combines pre/post satellite semantic change detection with Open-
StreetMap and is demonstrated on Indonesia’s 2018 tsunami; retrieved abstract-level evidence does not provide
comparable precision/recall or event-transfer results.[11] Work on automated road debris, flood depth and building
damage from airborne LiDAR/aerial imagery demonstrates the importance of higher-resolution data, but is not direct
evidence that medium-resolution Sentinel imagery can estimate those asset-level damages.[12]

Accordingly, distinguish hazard exposure (a road intersects a flood mask), observed image change, and verified struc-
tural damage/passability. Existing bridge work combines SAR coherence with crowdsourced and high-resolution
imagery, while road access methods use OSM and road-status information; the available studies do not support
treating a satellite cue alone as verified passability.[2][13]

6. Road-network disruption and settlement accessibility

The access literature connects flood extents or road-status reports to network/raster travel-time models, criticality,
and service access. In Cyclone Idai, Mozambique, raster and network methods differed by roughly 300,000 people
estimated to have lost healthcare access (about 800,000 versus 500,000); incomplete road mapping affected network
estimates more strongly. The study also identifies critical and backup road segments.[3]

A Sentinel-1-based Mandalay study links flood extents to network redundancy and healthcare access, while a Papua
New Guinea earthquake system combines OpenStreetMap and humanitarian road-status data for graph-theoretic
reachability. These are complementary: one estimates hazard intersection/criticality, the other uses reported road
condition.[14][13]

A short project can use OSM roads, settlement points and clinics, intersect roads with a flood mask, then compare
baseline and disrupted shortest-path travel time or reachable population. This connects satellite flood maps to net-
work criticality and access measures used in existing studies.[14][3] Make blockage assumptions explicit and test
alternatives; distinguish modelled exposure from observed closure.

7. Uncertainty, false positives and decision support

SAR false alarms can arise from permanent water, radar shadow/layover, wet soil, urban double-bounce and regis-
tration error; cloud and shadow challenge optical inputs. Fusion can reduce some ambiguities but also introduces
co-registration and missing-modality problems. The retrieved uncertainty-aware 2D/3D change-detection work ex-
plicitly attaches uncertainty/ambiguity to segmentation and 3D reconstruction, with expert review in earthquake
and wildfire settings, but provides no flood-specific calibration evidence in its available abstract.[15]

2

For flood mapping, uncertainty should be tested rather than represented only by a confidence-colored map: calibrate
probabilities on held-out events, inspect false positives by land cover and slope, report precision-recall trade-offs, and
include an abstain/review class for low-confidence areas. Uncertainty-aware 2D/3D change detection exists, but the
retrieved record does not establish a best flood-specific uncertainty method for response decisions.[15]

8. Automated, evidence-grounded situation reports

The operational evidence supports the need for interoperable, timely, confidence-aware information, rather than
proving that automated narrative reports improve response outcomes. A broad systematic review of disaster
situational-awareness technologies included 302 articles/after-action reports and identified delayed/unreliable
communications, time-intensive analysis/visualization and weak interoperability as constraints.[16]

A defensible student prototype would generate a compact structured report from computed outputs only: event/time
window, mapped flooded area, affected road length, settlements or services with changed travel times, top uncertain
regions, data lineage and links to the map/evidence. This addresses documented response challenges in delayed
analysis, visualization and interoperability, while avoiding a claim that generated prose itself has been shown to
improve decisions.[16]

Cross-study comparison and interpretation

Reported headline scores vary from IoU around 0.52 in one multimodal Sen1Flood11 setup to 0.96/0.94 in event tests
from another study; these are not a leaderboard because they differ in class targets, reference labels, geography, po-
larization, event selection and thresholding. Overall accuracy can hide rare flooded-pixel errors, so include classwise
precision, recall, F1, IoU, confusion matrices and event-level scores.[5][4]

Dimension

Inputs/preprocessing

Architecture/training

Resolution and timing

Geography and dataset size

Evaluation design

Evidence-weighted reading

Sentinel-1 amplitude and dual polarization are common;
multitemporal intensity/coherence can improve change
cues. SAR radiometric augmentation helped in one
benchmark; geometric augmentation hurt. Optical and
DEM inputs can help but co-registration and cloud gaps
matter.[4][6]
U-Net/FCN/FPN families are reproducible baselines. In
one comparison architecture differences were not
significant; data representation, labels, loss and split
design may matter as much or more.[4]
Sentinel-1 GRD supports broad-area flood extent but
not detailed structural diagnosis; finer-resolution
optical/airborne data are used for asset-scale debris and
damage. Flood-response timeliness is event-dependent;
the Baige map was produced within five days.[6][12]
Sen1Floods11, UrbanSARFloods and GEOID-Flood
provide increasing event/geographic diversity, yet class
imbalance, urban performance and label harmonization
remain.[1][10][7]
Event- or region-held-out testing is essential. Claims of
generalization need independent events and reported
per-event metrics; random tile splits alone are
insufficient for deployment claims. The retrieved
records often did not expose enough split detail to
verify this.[9][7]

3

Dimension

Compute/reproducibility

Evidence-weighted reading

Public data and code are reported for Sen1Floods11,
UrbanSARFloods and GEOID-Flood. GPU/runtime
requirements were generally not available in the
retrieved records; U-Net-level baselines are preferable
for a short project over reproducing large transformer
systems.[1][10][7]

Evidence-supported gaps (not novelty claims)

1. Event-independent validation remains a central need. Domain shift is explicitly documented; recent bench-
marks are designed to improve event diversity, but many abstract-level records do not reveal rigorous leave-
one-event-out performance.[9][7]

2. Urban flooding and class imbalance remain difficult. UrbanSARFloods explicitly reports this limitation and

questions whether common weighting/pretraining approaches suffice.[10]

3. Mountain debris/outburst floods are comparatively case-study driven in the retrieved evidence. Multisen-
sor terrain-aware examples exist, but available records do not establish broad transfer across terrain, sensors
or event types.[6][8]

4. Image-derived hazard, asset damage and actual passability are not interchangeable labels. Infrastructure
studies use mixed high-resolution imagery, coherence and crowdsourced inputs; network access results are
sensitive to road-map completeness.[2][3]

5. Uncertainty-to-action validation and evidence-grounded automated reporting are underdocumented in the
retrieved flood-specific studies. Uncertainty methods exist for broader disaster change detection and disaster
information systems, but the link from calibrated model uncertainty to response decisions was not established
here.[15][16]

Recommendation for a 15-day student project

Choose one event and one tractable output: Sentinel-1 flood extent → road exposure → settlement/service ac-
cessibility change, using a public benchmark event or a well-documented event with pre/post SAR and reference
labels. Sen1Floods11 and UrbanSARFloods provide public starting points.[1][10] Use a simple threshold/rule-based
comparator and U-Net (or RF if compute/data preparation is constrained); compare single-date with pre/post change
features and optionally add DEM slope. Hold out a whole event or spatial block, not random adjacent chips. Report
precision, recall, F1, IoU, confusion matrix, and false-positive examples by land cover; then convert the mask to road
intersections and compare at least two closure assumptions in a graph-based access analysis. Existing access studies
demonstrate sensitivity to methods and road-data completeness.[3] Keep the narrative report templated and gener-
ated from measured outputs, with a confidence/limitations section rather than open-ended image interpretation.

A realistic 15-day scope is one flood map, one honest held-out evaluation, and one transparent access scenario,
not a new multimodal foundation model or validated bridge-damage classifier. The highest-value contribution is
likely careful split design, error analysis and traceable impact translation, not claiming a new architecture. Open-
code availability for Sen1Floods11 and UrbanSARFloods makes those stronger starting points than unverified recent
methods.[1][10]

Review coverage and verification limits

This is an in-session evidence synthesis, not a formal registered or platform-run systematic review. Discovery used
academic search queries organized around the requested topics; the delivered matrix contains 19 selected source-
linked records. Most study details were available as abstracts or indexed summaries; no comprehensive full-text
retrieval and extraction was completed. Consequently, papers whose full-text or split/compute details could not be
verified are explicitly marked in the matrix. Particularly thin areas in this search were flood-specific uncertainty
calibration, automated evidence-grounded report evaluation, and satellite-only road/building damage labels. The
matrix links to DOI, publisher or available source pages where retrieved; a linked record does not imply full-text
verification.

4

References

1.

2.

3.

4.

5.

6.

7.

8.

9.

10.

11.

12.

Bonafilia D, Tellman B, Anderson T, Issenberg E (2020) Sen1Floods11: a georeferenced dataset to train and test
deep learning flood algorithms for Sentinel-1. 2020 IEEE/CVF Conference on Computer Vision and Pattern
Recognition Workshops (CVPRW). https://doi.org/10.1109/CVPRW50498.2020.00113

Kopiika N, Karavias A, Krassakis P, et al (2024) Rapid post-disaster infrastructure damage characterisation
using remote sensing and deep learning technologies: A tiered approach. Automation in Construction. https:
//doi.org/10.1016/j.autcon.2024.105955

Petricola S, Reinmuth M, Lautenbach S, et al (2022) Assessing road criticality and loss of healthcare accessibil-
ity during floods: the case of Cyclone Idai, Mozambique 2019. International Journal of Health Geographics.
https://doi.org/10.1186/s12942-022-00315-2

Helleis M, Wieland M, Krullikowski C, et al (2022) Sentinel-1-Based Water and Flood Mapping: Benchmarking
Convolutional Neural Networks Against an Operational Rule-Based Processing Chain. IEEE Journal of Se-
lected Topics in Applied Earth Observations and Remote Sensing. https://doi.org/10.1109/jstars.2022.3152127

Bai Y, Wu W, Yang Z, et al (2021) Enhancement of Detecting Permanent Water and Temporary Water in Flood
Disasters by Fusing Sentinel-1 and Sentinel-2 Imagery Using Deep Learning Algorithms: Demonstration of
Sen1Floods11 Benchmark Datasets. Remote Sensing. https://doi.org/10.3390/rs13112220

Yang Z, Wei J, Deng J, et al (2021) Mapping Outburst Floods Using a Collaborative Learning Method Based
on Temporally Dense Optical and SAR Data: A Case Study with the Baige Landslide Dam on the Jinsha River,
Tibet. Remote Sensing. https://doi.org/10.3390/rs13112205

Chiriaco G, Barco L, Bragagnolo A, et al (2026) GEOID-Flood: A Large-Scale Multi-Modal Benchmark Dataset
for Flood Segmentation

Tsutsui K, Miyazaki S, Nakagawa H, et al (2004) Data fusion techniques of heterogeneous sensor images for
debris hazard assessments. IGARSS 2004 2004 IEEE International Geoscience and Remote Sensing Sympo-
sium. https://doi.org/10.1109/IGARSS.2004.1369035

Turkmenli I, Kayabol K, Aptoula E (2025) A Comparative Domain Generalization Study for SAR Image-Based
Flood Segmentation. Joint Urban Remote Sensing Event. https://doi.org/10.1109/JURSE60372.2025.11075977

Zhao J, Xiong Z, Zhu XX (2024) UrbanSARFloods: Sentinel-1 SLC-Based Benchmark Dataset for Urban and
Open-Area Flood Mapping. 2024 IEEE/CVF Conference on Computer Vision and Pattern Recognition Work-
shops (CVPRW). https://doi.org/10.1109/CVPRW63382.2024.00047

Gupta A, Welburn E, Watson S, Yin H (2019) Post Disaster Mapping With Semantic Change Detection in Satel-
lite Imagery. 2019 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW).
https://doi.org/10.1109/CVPRW.2019.00062

Axel C (2017) Towards Automated Analysis of Urban Infrastructure after Natural Disasters using Remote
Sensing

13. Warnier M, Alkema V, Comes T, Walle BAV de (2020) Humanitarian access, interrupted: dynamic near real-
time network analytics and mapping for reaching communities in disaster-affected countries. OR spectrum.
https://doi.org/10.1007/s00291-020-00582-0

14.

Kwant M, Groen F de, Marle MJE van, et al (2021) Near Real-Time Flood Impact Analysis on Road Networks.
https://doi.org/10.5194/EGUSPHERE-EGU21-16545

5

15.

16.

Hümmer C, Lallement D, Youssefi D (2024) Uncertainty-Aware 2d/3d Change Detection for Natural Disaster
Response. IEEE International Geoscience and Remote Sensing Symposium. https://doi.org/10.1109/IGARSS
53475.2024.10642271

Kedia T, Ratcliff J, O’Connor M, et al (2020) Technologies Enabling Situational Awareness During Disaster
Response: A Systematic Review. Disaster Medicine and Public Health Preparedness. https://doi.org/10.1017/
dmp.2020.196

6


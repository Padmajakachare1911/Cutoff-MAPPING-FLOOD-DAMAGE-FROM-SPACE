Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Cutoff: terrain-gated SAR flood/debris
mapping with evidence-graded settlement
isolation
Multimodal AI Hackathon 2026 · Track B "Mapping Flood Damage from Space" · prepared
10 Oct 2026
Labels used throughout: [V] verified by me against a primary source in this session · [S]
appears only in your supplied documents, not re-verified · [D] design decision · [H]
hypothesis to test · [?] open fact that must be checked.
1. Executive decision
Build "Cutoff": one pipeline that takes an area + flood date and runs raw Sentinel-1 (same-
track pre/post) → a trained flood-segmentation model plus a terrain-gated change
detector → OSM exposure → a scenario-based road-graph analysis of which settlements
lose road access to the nearest town/hospital → a dashboard and a template-generated
one-page situation report. It is evaluated three ways: on Kuro Siwo's official held-out
events (stratified by terrain slope), on the Trishuli event against EMSR927 with zero
tuning on EMSR927, and with a sensitivity study of the cut-off result to closure
assumptions and OSM completeness.
AI component chosen: flood segmentation model (25% of the score, and the PS
explicitly asks to show performance on unseen Himalayan scenes). The situation report is
generated from a JSON of computed numbers by a template, so no language model can
invent a number; the Nepali copilot is a stretch goal, not a requirement under this option.
Three decisions that differ from your supplied research, each with a verified reason:
1. Training data = Kuro Siwo only (Sen1Floods11 optional, post-only baseline). GEOID-
Flood [V] and MMFlood [V] are built from Copernicus EMS delineations, are not on the
PS dataset list, and GEOID-Flood spans 2016–2026, so it may contain EMSR927 itself.
The PS says EMS products may only be used to check results, and breaking this rule
means disqualification. The same logic rules out IBM ImpactMesh (EMS-derived labels,
per your repo report [S]) and WorldFloods.
2. No Swin/dual-stream transformer, no conformal stack in the first build. There are no
debris labels, Kuro Siwo's own paper reports DEM/slope inputs give only marginal gains
[V], and the budget is 15 days. A U-Net, terrain gating and temperature scaling are
Page 1 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
enough to defend.
3. "Himalayan unseen scenes" is proven by Trishuli (never trained on) plus slope-
stratified Kuro Siwo test events, because no labelled Himalayan flood training data
was identified in any supplied document.
Top three risks: live preprocessing latency on judge-chosen areas; no Himalayan labels
beyond EMSR927; incomplete pre-event OSM in remote valleys. Mitigations are in section
16 of this document.
2. Official PS and track compliance matrix
Source key: PS = Track_B.pdf / Space_Track.pdf (identical content).
| # Requirement | Source | M/O | Our implementation | Verification |
| ------------- | ------ | --- | ------------------ | ------------ |
R1 System takes an PS M CLI and dashboard Run on ≥2 non-Trishuli AOIs
| area and a flood | Requirements |     | accept AOI           |     |
| ---------------- | ------------ | --- | -------------------- | --- |
| date             |              |     | polygon/bbox + event |     |
date; nothing hard-
coded to Trishuli
R2 Where did the PS Q1 M Same-track S1 change Overlap with EMSR927; S2 coverage
| flood hit: S1    |     |     | + trained model; S2   | flag |
| ---------------- | --- | --- | --------------------- | ---- |
| before/after, S2 |     |     | only as corroboration |      |
| when clear       |     |     | where SCL is clear    |      |
R3 What was PS Q2 M Hazard ∩ OSM; Recall of EMS-damaged features
| damaged: OSM      |     |     | reported as exposed, | (check-only) |
| ----------------- | --- | --- | -------------------- | ------------ |
| buildings, roads, |     |     | never "destroyed"    |              |
bridges,
estimate which
were hit
R4 Who is cut off: PS Q3 M NetworkX graph, Synthetic-graph tests; EMS-closure
| no road link to |     |     | three closure          | replay |
| --------------- | --- | --- | ---------------------- | ------ |
| nearest         |     |     | scenarios, four status |        |
| town/hospital   |     |     | classes                |        |
R5 AI component: PS AI M Flood segmentation Section 11 protocol
| choose one | component |     | model |     |
| ---------- | --------- | --- | ----- | --- |
R6 Show PS AI option 1 M Trishuli (no training, Metrics table in report
| performance on |     |     | no tuning) + slope |     |
| -------------- | --- | --- | ------------------ | --- |
| unseen         |     |     | strata             |     |
Himalayan
scenes
R7 Bonus: trace PS Bonus O pyflwdir flow path + Path follows Lhende→Bhote
| flood path       |     |     | HAND corridor + | Koshi→Trishuli |
| ---------------- | --- | --- | --------------- | -------------- |
| downstream, list |     |     | OSM places      |                |
settlements
Page 2 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| # Requirement | Source | M/O | Our implementation | Verification |
| ------------- | ------ | --- | ------------------ | ------------ |
R8 Case study vs PS Case study M eval/emsr927.py, Agreement + disagreement
| EMSR927 |     |     | check-only | taxonomy |
| ------- | --- | --- | ---------- | -------- |
R9 Map dashboard PS Output M Streamlit + Demo, usability pass
| + one-page |     |     | Jinja→PDF |     |
| ---------- | --- | --- | --------- | --- |
system-
generated
situation report
R10 GitHub repo PS M README.md, make Fresh-clone run by a teammate
| with README on | Deliverables |     | targets, pinned env |     |
| -------------- | ------------ | --- | ------------------- | --- |
how to run
| R11 Report ≤6 pages | PS           | M   | docs/report/,       | Page count |
| ------------------- | ------------ | --- | ------------------- | ---------- |
| incl. limitations   | Deliverables |     | limitations written |            |
from section 11 failure
data
| R12 3-minute demo | PS           | M   | Script in section 17 | Timed run |
| ----------------- | ------------ | --- | -------------------- | --------- |
| video             | Deliverables |     |                      |           |
R13 Attributions (3 PS Attribution M ATTRIBUTION.md; Grep check in CI
| exact strings) + |     |     | footer on dashboard,    |     |
| ---------------- | --- | --- | ----------------------- | --- |
| training-dataset |     |     | report and sitrep; cite |     |
| citations        |     |     | Bountos et al. 2024     |     |
R14 Allowed inputs PS Data rules M Config allow-list; tests/test_no_reference_leak.py
| only: S1, S2,  |     | (disqualifying) | pipeline never     |     |
| -------------- | --- | --------------- | ------------------ | --- |
| Copernicus     |     |                 | imports eval; test |     |
| DEM, pre-event |     |                 | asserts OSM date < |     |
| OSM, listed    |     |                 | 2026-08-26         |     |
training sets
| R15 OSM snapshot | PS Datasets | M   | Default 2026-07-27, | Test |
| ---------------- | ----------- | --- | ------------------- | ---- |
| before 26 Aug    |             |     | asserted            |      |
2026 (latest
available 27 Jul
2026 per PS)
| R16 Published   | PS Datasets | M   | Any exported OSM-   | README |
| --------------- | ----------- | --- | ------------------- | ------ |
| modified OSM    |             |     | derived GeoJSON     |        |
| data stays ODbL |             |     | carries ODbL notice |        |
R17 Compare same PS Tip Strongly Pair selector enforces Log + test
| orbit track only |     | implied | relative orbit; cross- |     |
| ---------------- | --- | ------- | ---------------------- | --- |
| (same time of    |     |         | track only in a        |     |
| day, 12 days     |     |         | labelled ablation      |     |
apart)
R18 Run end-to-end PS Data rules, M Section 8 pipeline, Runtime test E7
| from raw data for | Evaluation |     | caching, timing tests |     |
| ----------------- | ---------- | --- | --------------------- | --- |
any judge-
chosen
area/date, live
Page 3 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| # Requirement | Source         | M/O | Our implementation    | Verification |     |
| ------------- | -------------- | --- | --------------------- | ------------ | --- |
| R19 No victim | PS             | M   | Maps only; disclaimer | Review       |     |
| images;       | Responsibility |     | on every output       |              |     |
educational
prototype
wording
R20 Limitations: what PS Limitations M e.g. no early warning Section 6 and report
| the system |     |     | given revisit time |     |     |
| ---------- | --- | --- | ------------------ | --- | --- |
cannot do
Scoring weights from the PS: flood/damage mapping 30%, AI component 25%, cut-off
analysis 20%, report/Q&A/honesty 15%, dashboard/report usability 10%. Effort allocation
follows these.
3. Research audit
3.1 Source ledger
| Source |     | Type / date | Verified by me? | What I used | Limits |
| ------ | --- | ----------- | --------------- | ----------- | ------ |
Track_B.pdf, Space_Track.pdf Official PS, [V] read in full All rules and weights Illustrative images only
2026
Kuro Siwo GitHub README, github.com/Orion- Repo page, [V] main.py --method Dataset download size
| AI-Lab/KuroSiwo |     | fetched |     | --backbone --dem - | not stated |
| --------------- | --- | ------- | --- | ------------------ | ---------- |
|                 |     | today   |     | -slope; GRD + SLC; |            |
GeoTIFFs and
webdatasets on
Hugging Face;
polygons repo;
weights for FloodViT
and SNUNet
(Dropbox); SNAP
preprocessing XML
in configs/; MIT
LICENSE file while
README text says
CC BY
Page 4 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Source Type / date Verified by me? What I used Limits
Bountos et al., NeurIPS 2024 D&B (arXiv Peer- [V] abstract and 43 events; 67,490 I did not read the full
2311.12056) reviewed tables via labelled 224×224 paper; event geography
search patches at 10 m; 2 not seen
pre + 1 post S1 per
event; DEM and
slope; classes no-
water / permanent
water / flood; 10 test
events; best models
>80% F1 on flood;
DEM/slope gives
marginal gains;
permanent water is
the weakest class
CEMS EMSR927 page, Official, 26 [V] Activation scope: Vector package contents
mapping.emergency.copernicus.eu/news/flood- Aug 2026 flood extent + not seen [?]
in-nepal-emsr927/ damage assessment;
"reportedly" a GLOF
EU Space "Image of the day" ×2 Official [V] Four AOIs; >240 One AOI view only
buildings destroyed
and 32 damaged in
the Syapru Besi view;
Sentinel-2 scenes of
12 and 27 Aug near
Betrawati/Gerkhu
show wider
sediment-filled
channel
Community catalog "Nepal Floods 2026" (gee- Secondary, [V] Flood at ~02:52 UTC Secondary source; not
community-catalog.org) updated 31 26 Aug; ~100 km an allowed input
Aug runout; casualty and
damage figures
explicitly provisional;
Planet/Maxar
imagery is CC BY-NC
and mostly cloudy
GEOID-Flood (arXiv 2608.02315) Preprint [V] abstract + CEMS-derived, 219 Not on PS list; leakage
2026 §3 events, S1 RTC + S2 + risk
GLO-30, CC BY 4.0;
fusion best for
transient flooding
MMFlood (IEEE Access 2022) Peer- [V] abstract 95 EMS events, S1 + EMS-derived
reviewed DEM + hydrography
ICIMOD "Flood data of Nepal, 11 Aug 2017" (doi Dataset, CC [V] snippet S1-derived flood Likely lowland; format
10.26066/RDS.33614) BY 4.0 extent over Nepal: unseen
candidate check-
only scene
NDRRMA Sitrep #1, Rasuwa glacial flood, July Official [V] snippet A 2025 outburst Reference labels
2025 flood on the same unknown [?]
corridor: candidate
second Himalayan
scene
Page 5 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Source | Type / date | Verified by me? | What I used | Limits |
| ------ | ----------- | --------------- | ----------- | ------ |
ohsome API docs (docs.ohsome.org) Official docs [V] snippet time and filter Response limits to test
parameters;
geometry endpoint
Elicit review PDF + sources.xlsx AI-assisted [V] read; Gap list; 15-day Abstract-level only (its
|     | literature | spreadsheet = | scope               | own caveat); PDF says 19 |
| --- | ---------- | ------------- | ------------------- | ------------------------ |
|     | review     | 16 rows       | recommendation;     | papers, sheet has 16     |
|     |            | matching the  | dual-pol,           |                          |
|     |            | PDF's         | radiometric-aug and |                          |
|     |            | references    | held-out-event      |                          |
advice
Doc A: GitHub repo investigation (pasted agent AI agent [S] Licence notes (GPL- Rankings and "7/7"
| log) | report |     | 3.0 reference-only; | scores not reproducible |
| ---- | ------ | --- | ------------------- | ----------------------- |
Sen1Floods11 no
licence)
Doc B: deep-research briefing (pasted) AI report [S] Reporting rule Numbers from
|     |     |     | (exposure ≠       | Springer/ILO/UNOSAT |
| --- | --- | --- | ----------------- | ------------------- |
|     |     |     | damage); closure- | not re-checked      |
scenario structure;
repo list
Doc C: AI report [S] Physical failure Several inconsistencies,
Himalayan_Flood_Mapping_AI_Assessment modes; falsification- see 3.2
| PDF |     |     | experiment idea |     |
| --- | --- | --- | --------------- | --- |
Sen1Floods11 (Bonafilia, CVPRW 2020) Peer- [S] via Elicit 4,831 chips, 11 events, Single-date S1
|     | reviewed |     | mostly auto- |     |
| --- | -------- | --- | ------------ | --- |
generated labels
3.2 Contradictions and decisions
| Claim in supplied material | Problem |     | Decision |     |
| -------------------------- | ------- | --- | -------- | --- |
Doc A: no repo covers more than 4 Doc B lists repos that Claim novelty only for
of 7 components, so the brief is already do S1 change engineering and
| "genuinely novel" | detection + OSM road |     | evaluation |     |
| ----------------- | -------------------- | --- | ---------- | --- |
impact, a dashboard, and
flood-to-healthcare
routing [S]
| Doc A: fork IBM ImpactMesh | EMS-derived labels |     | Reject |     |
| -------------------------- | ------------------ | --- | ------ | --- |
cannot be inputs; not on
PS list; I did not verify it
Doc B: fine-tune on Sen1Floods11 WorldFloods not on PS WorldFloods out;
and/or WorldFloods list; Sen1Floods11 has one Sen1Floods11 optional
S1 date, so it cannot teach post-only baseline
pre/post change
Page 6 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Claim in supplied material | Problem | Decision |
| -------------------------- | ------- | -------- |
Elicit/Doc B: use GEOID-Flood, EMS-derived (GEOID) or Related work only
| UrbanSARFloods | not on the list; leakage or |     |
| -------------- | --------------------------- | --- |
disqualification risk
Doc C: Kuro Siwo models "fail to Plausible because Kuro Test it as H2/H3, do not
| detect debris" and DEM is | Siwo has no debris class | assume |
| ------------------------- | ------------------------ | ------ |
| essential                 | [V], but unevidenced;    |        |
paper says DEM is
marginal [V]
Doc C: dB thresholds (−4/+3/+8 Thresholds cited to a No hard-coded dB limits;
dB), HAND >15 m vs <30 m vs >5 Chamoli water-quality scene-adaptive
m, blank slope limit paper, internally thresholds (section 8)
inconsistent
Doc C: three-fold plan training on No labelled Himalayan Replace with Kuro Siwo
Annapurna/Karnali/Chamoli basins flood data identified events + Trishuli zero-
tuning check
| Doc C: isolated-village | I found no evidence | Validate closed |
| ----------------------- | ------------------- | --------------- |
precision/recall against CEMS CEMS publishes isolated edges/bridges against
| maps | villages [?] | EMS damage layers; |
| ---- | ------------ | ------------------ |
replay routing
Doc C: Swin dual-stream, temporal Not deliverable in 15 days; Simple U-Net,
attention, conformal, super- no debris labels temperature scaling
resolution
Doc C: ascending Track 56 vs Unverifiable here (no Tracks discovered at run
| descending Track 63 | CDSE query possible) | time |
| ------------------- | -------------------- | ---- |
Event cause and casualty counts Sources disagree and are Never print casualty
differ (PS: glacier collapse; CEMS: provisional figures; use "reported"
| "reportedly" GLOF; catalog: |     | wording |
| --------------------------- | --- | ------- |
unresolved; death tolls rising)
3.3 What I could not verify
Sentinel-1 acquisitions, relative orbits and download latency for the corridor; contents of
Kuro Siwo's  grd_preprocessing.xml  (units, DEM used, speckle filter); Kuro Siwo event
geography and download size; input format of the released weights; EMSR927 vector
Page 7 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
layers and legend; the code of repos named in Docs A/B (ImpactMesh, Prithvi, healthcare-
access-idai, SAR-Flood-Detection); 2026 Sentinel Hub quotas on CDSE; pyflwdir API
details. Each is a Milestone 2–3 check.
4. Prior-art comparison matrix
System Approach / data Reported Limits What Cutoff Already done
|     |     | evidence |     | adds | elsewhere? |
| --- | --- | -------- | --- | ---- | ---------- |
Kuro Siwo + Multi-temporal >80% F1 Water classes Slope- Training/benchmark
BlackBench [V] GRD/SLC, DEM+slope, (flood) on 10 only; DEM stratified yes; strata and gating
|     | U-                   | test events | marginal; test   | reporting,      | no evidence |
| --- | -------------------- | ----------- | ---------------- | --------------- | ----------- |
|     | Net/SNUNet/FloodViT- | (abstract)  | geography not    | terrain gating, |             |
|     | type models          |             | slope-stratified | Himalayan       |             |
|     |                      |             | in what I saw    | check           |             |
Sen1Floods11 [S] 4,831 chips, hand- Basis of many Weak labels, Not used for n/a
|     | labelled + weak labels | papers | single date | training |     |
| --- | ---------------------- | ------ | ----------- | -------- | --- |
GEOID-Flood, EMS-derived masks with Fusion best Barred by PS Related work n/a
| MMFlood [V] | S1/DEM(/S2) | for transient | rules | only |     |
| ----------- | ----------- | ------------- | ----- | ---- | --- |
water
SAR-Flood- Refined Lee, change Workflow, no Heuristic; Learned model Road-flooding yes;
Detection detection, JRC water benchmark shadow/wet + held-out benchmarked
(JakubNiedzwiedz) removal, slope filter, debris evaluation + evaluation not seen
| [S] | OSM flooded roads |     | confusion | graph isolation |     |
| --- | ----------------- | --- | --------- | --------------- | --- |
sentinel1-sar-flood- ASF search, co- Workflow No Same-track Dashboard yes
| mapping           | registration, change |     | routing/OSM | enforcement + |     |
| ----------------- | -------------------- | --- | ----------- | ------------- | --- |
| (AliForghani) [S] | detection, Streamlit |     | impact seen | routing       |     |
healthcare-access- S1 flood + OSM + Raster vs Flood is a Closure- Cut-off concept yes
idai / Petricola 2022 OpenRouteService network mask; no scenario range,
| [S] | isochrones | methods   | bridge logic or | bridge rule,  |     |
| --- | ---------- | --------- | --------------- | ------------- | --- |
|     |            | differ by | uncertainty     | status        |     |
|     |            | ~300,000  |                 | "unknown" for |     |
|     |            | people    |                 | OSM gaps      |     |
(≈800k vs
500k)
DISruptionMap OSM + depth threshold Preprint Depth rule Hazard Accessibility yes
| (arXiv 2410.05286) | (27 cm) |     | unsuited to  | probability, not |     |
| ------------------ | ------- | --- | ------------ | ---------------- | --- |
| [S]                |         |     | debris/scour | depth            |     |
Baige outburst-flood S1/S2/DEM + RF OA 92.3%, κ Single case Multi-event Mountain fusion yes
| study (Yang 2021) |     | 0.89, single |     | evaluation |     |
| ----------------- | --- | ------------ | --- | ---------- | --- |
| [S]               |     | event        |     |            |     |
CEMS EMSR927 [V] Analyst VHR product Reference Not Used as check Reference
|     |     |     | reproducible | only |     |
| --- | --- | --- | ------------ | ---- | --- |
No row contains our exact combination, but I cannot prove absence: I searched, I did not
exhaust.
Page 8 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
5. Evidence-backed gap
| Candidate gap        | PS weight | Evidence it      | Feasible in 15 | Verdict |
| -------------------- | --------- | ---------------- | -------------- | ------- |
|                      |           | exists           | days           |         |
| G1 Mountain false    | 30% +     | PS asks for it;  | Yes            | Chosen  |
| alarms               | 25%       | Elicit gap 3     |                |         |
| (shadow/layover,     |           | (mountain debris |                |         |
| steep slopes) and no |           | studies are case |                |         |
| Himalayan held-out   |           | studies) [S];    |                |         |
| proof                |           | radar-geometry   |                |         |
physics
(textbook)
| G2 Hazard-to-        | 20% | Elicit gap 4;     | Yes | Chosen |
| -------------------- | --- | ----------------- | --- | ------ |
| passability-to-      |     | Petricola raster- |     |        |
| isolation link with  |     | vs-network        |     |        |
| explicit assumptions |     | difference [S]    |     |        |
G3 Debris vs water Part of Q1 No debris class Only rule- Secondary,
| separation |     | in Kuro Siwo [V]; | based, no labels | flagged    |
| ---------- | --- | ----------------- | ---------------- | ---------- |
|            |     | opposite          |                  | hypothesis |
backscatter
signs suggested
[S]
G4 Calibrated Part of Elicit gap 5 [S] Light version Included, light
| uncertainty | honesty |     | (temperature |     |
| ----------- | ------- | --- | ------------ | --- |
|             | score   |     | scaling)     |     |
G5 Grounded reports 15% / 10% Elicit: not shown Easy (template) Deliverable,
|                   |      | to improve   |     | not a        |
| ----------------- | ---- | ------------ | --- | ------------ |
|                   |      | outcomes [S] |     | contribution |
| G6 Foundation-    | none | Unproven for | No  | Rejected     |
| model fine-tuning |      | debris       |     |              |
6. Final project definition and defensible novelty
Title: Cutoff: terrain-gated, same-track SAR flood/debris mapping with evidence-graded
settlement isolation.
Page 9 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Pitch: Rescuers need to know where the valley floor changed and which villages lost their
road. Cutoff gives that answer from free satellite data for any valley and date, says how
sure it is, and shows which assumptions would change the answer.
Users: disaster responders and analysts (educational prototype, not operational).
What existing systems fail to address (supported part): flood extent, flooded roads and
healthcare isolation each exist separately [S]; I found no single open workflow that
couples same-track change detection, terrain gating, a trained model with slope-stratified
held-out evaluation, and closure-scenario isolation analysis.
Exact contribution
1. Engineering: automated same-track pair selection plus terrain gating (layover/shadow,
slope, HAND) feeding a trained model, running from raw data for any AOI/date.
2. Evaluation: slope-stratified held-out metrics, a zero-tuning Trishuli check, and a cut-off
sensitivity study (closure assumption, OSM completeness).
3. Application: Himalayan valley adaptation with a rule-based "disturbance" layer for what
the water model cannot see.
Not claimed: research novelty (no new architecture or loss), operational readiness,
validated damage or debris classification, or uniqueness.
Evidence needed to defend each claim: (1) a run log on two non-Trishuli AOIs; (2) tables
E1–E2, E4 in section 11; (3) table E6 in section 11.
Limitations to state: revisit gaps (cannot warn of a sudden collapse); 10 m pixels versus
narrow channels; imagery may show the flood after it peaked; wet smooth mud can look
like water; OSM gaps create false "cut-off" results; Kuro Siwo labels water, not debris;
EMSR927 is an analyst product, not ground truth.
7. Research questions and hypotheses
All are [H] until measured.
ID Hypothesis Test Falsified if
H1 Pre-mean + post + difference E3 Flood IoU gain <2 pts
inputs beat post-only on held- on test events
out events
Page 10 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| ID Hypothesis | Test | Falsified if |
| ------------- | ---- | ------------ |
H2 Terrain gating cuts false-positive E2/E3 Either bound missed
area on slope >15° by ≥30% with
≤5 pts recall loss
| H3 Cross-track pairs give more  | E5  | No difference beyond |
| ------------------------------- | --- | -------------------- |
| false positives on steep stable |     | noise                |
terrain than same-track pairs
| H4 Fixed Kuro Siwo-tuned        | E1 vs E4 | Larger drop (reported |
| ------------------------------- | -------- | --------------------- |
| thresholds transfer to Trishuli |          | honestly)             |
with F1 within 15 pts of the in-
domain test
| H5 The cut-off set changes | E6  | Set stable (then say |
| -------------------------- | --- | -------------------- |
| materially across closure  |     | so)                  |
scenarios and under 10–20%
OSM edge dropout
| H6 Backscatter increase  | E4 visual + EMS     | No class-wise |
| ------------------------ | ------------------- | ------------- |
| (roughness) and decrease | agreement per class | agreement     |
(water/smooth mud) separate
two hazard types along the
valley floor
Thresholds in the table are targets I set before experiments, not promises.
Page 11 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
8. End-to-end architecture
Input: AOI polygon + event date (+ OSM date, default 2026-07-27)
|
[1 DISCOVER] CDSE STAC/OData -> same-track manifest: 1 post + up to 3 pre at
-12/-24/-36 d
|
[2 PREPROCESS] S1: SNAP GPT (Kuro Siwo graph) -> dB VV/VH, shadow mask |
DEM: GLO-30 -> slope, HAND, flow-dir
| S2 (optional): L2A + SCL -> pre composite, post, clear mask
|
[3 HAZARD] A: U-Net(pre-mean, post, difference, slope) -> p(flood),
p(permanent water)
| B: rule-based disturbance: |delta| > k * sigma_stable inside
HAND corridor
| C: gating (shadow/layover, slope, HAND) + optional S2
corroboration -> class + confidence
|
[4 OSM] ohsome snapshot -> buildings, roads (+bridge tag), places,
hospitals
[5 EXPOSURE] hazard ∩ OSM -> exposed buildings, road km, bridges (by
confidence tier)
[6 NETWORK] graph + 3 closure scenarios -> connected / degraded / cut-off /
unknown
[7 BONUS] flow path from a point -> HAND corridor -> settlements along it
[8 OUTPUT] results.json (single source of truth) -> Streamlit dashboard +
one-page sitrep PDF
Separate, check-only: eval/ reads reference/EMSR927 -> metrics (never
imported by stages 1-8)
Data flow, with schemas
# Stage Input Output
1 Pair selection AOI, date, STAC/OData pairs.json : product IDs, relative
orbit, direction, datetimes, coverage
fraction
2 S1 GRD zips, DEM s1_{date}.tif (2 bands VV/VH, dB,
preprocessing 10 m, UTM 45N for Trishuli),
shadow.tif
Page 12 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| # Stage   | Input        | Output  |              |             |     |
| --------- | ------------ | ------- | ------------ | ----------- | --- |
| 3 Terrain | GLO-30 tiles | dem.tif | ,  slope.tif | ,  hand.tif | ,   |
flowdir.tif
| 4 Hazard | stack above | p_flood.tif |  (float),  | hazard.gpkg |     |
| -------- | ----------- | ----------- | ---------- | ----------- | --- |
(polygons: class, confidence tier,
reason flags)
| 5 OSM | AOI, date |     |     |     |     |
| ----- | --------- | --- | --- | --- | --- |
osm_{layer}.gpkg
| 6 Exposure | hazard + OSM              | exposure.gpkg     | , counts in JSON |              |     |
| ---------- | ------------------------- | ----------------- | ---------------- | ------------ | --- |
| 7 Network  | roads, places, hospitals, | edges_status.gpkg |                  | ,            |     |
|            | hazard                    | settlements.gpkg  |                  |  (status per |     |
scenario)
| 8 Report | results.json | dashboard | ,  sitrep.pdf |     |     |
| -------- | ------------ | --------- | ------------- | --- | --- |
Role of each component: SNAP GPT does radiometric/terrain processing; pyflwdir
derives HAND and flow paths; the U-Net supplies water probability; the rule-based
detector covers what Kuro Siwo cannot label; NetworkX does routing; Streamlit and Jinja
only read artifacts.
Core contribution vs the rest: stages 3 and 6 are the contribution; stages 1–2, 4–5 and 8
are supporting engineering.
Scene-adaptive thresholds [D]. For the disturbance layer, estimate sigma_stable as the
robust spread (MAD) of the dB difference over pixels that cannot be flooded (HAND >100
m), per slope/aspect bin; flag |difference| > k·sigma_stable (k=3, set before looking at
EMSR927) and keep connected areas above a minimum size. The positive and negative
signs are reported separately. This avoids borrowing dB limits that I could not source.
Gating [D]. Mask layover/shadow from DEM + look geometry; downgrade (not delete)
water-class pixels on steep slopes or high HAND to "possible"; physical limits are set from
the training validation events, and the HAND search corridor is a conservative physical
choice (start at 60 m, state it).
Failure cases and recovery
Page 13 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Failure |     | Detection |     | Recovery |     |
| ------- | --- | --------- | --- | -------- | --- |
No same-track post- Pair selector returns empty Report "no valid observation" for
| event scene |     |     |     | the AOI; list next acquisition |     |
| ----------- | --- | --- | --- | ------------------------------ | --- |
date; never fall back silently to
cross-track
Cross-track only Orbit mismatch Run only as labelled ablation,
flagged "not comparable"
Layover/shadow pixels Shadow mask Output "no valid observation"
class, excluded from metrics
Persistent cloud (S2) SCL clear fraction S2 layer off; confidence not
upgraded
Wet smooth mud ≈ Low-backscatter inside Tag "water or smooth mud
| water |     | disturbance corridor |     | (ambiguous)" |     |
| ----- | --- | -------------------- | --- | ------------ | --- |
Missing bridge/trail in Settlement has no baseline Status "unknown", never "cut
| OSM |     | route |     | off" |     |
| --- | --- | ----- | --- | ---- | --- |
Download or SNAP Exit code, size check Retry; cached scene fallback;
| failure |     |     |     | fast-mode preprocessing |     |
| ------- | --- | --- | --- | ----------------------- | --- |
9. Data and labelling strategy
| Dataset | Role | Modality / | Labels / licence | Access | Known limits |
| ------- | ---- | ---------- | ---------------- | ------ | ------------ |
resolution
Sentinel-1 GRD Inputs VV/VH, 10 m Copernicus CDSE free account 12-day repeat,
| IW  | (pre/post) |     | open licence [V |     | geometry limits |
| --- | ---------- | --- | --------------- | --- | --------------- |
per PS]
Sentinel-2 L2A Optional 10–20 m Open licence CDSE Monsoon cloud
corroboration
Copernicus Slope, HAND, 30 m Attribution AWS open data or CDSE [?] Smooths narrow
| GLO-30 DEM | shadow |     | string required |     | gorges |
| ---------- | ------ | --- | --------------- | --- | ------ |
OSM via Buildings, Vector ODbL https://api.ohsome.org/v1 Remote-area
| ohsome, 2026- | roads, bridges, |     |     |     | completeness |
| ------------- | --------------- | --- | --- | --- | ------------ |
| 07-27         | places,         |     |     |     |              |
hospitals
Page 14 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Dataset | Role | Modality / | Labels / licence | Access | Known limits |
| ------- | ---- | ---------- | ---------------- | ------ | ------------ |
resolution
Kuro Siwo Training + 224×224 Manual labels, 3 GitHub + Hugging Face Size to be
(GRD) validation + patches, 10 classes; MIT file checked [?];
|     | official test | m, 2 pre + 1 | vs CC BY     |     | labels are water, |
| --- | ------------- | ------------ | ------------ | --- | ----------------- |
|     |               | post, DEM,   | README [V],  |     | not debris        |
|     |               | slope        | cite Bountos |     |                   |
2024
Sen1Floods11 Post-only S1 single No licence file; GitHub Weak labels, no
| (optional) | baseline only | date | mirrors CC BY |     | pre-event scene |
| ---------- | ------------- | ---- | ------------- | --- | --------------- |
4.0 [S]
EMSR927 Check only Vectors Credit mapping.emergency.copernicus.eu Layers/legend
|     |     |     | "European |     | unseen [?] |
| --- | --- | --- | --------- | --- | ---------- |
Union,
Copernicus
Emergency
Management
Service data"
Other Check only, if S1-derived CC BY 4.0 ICIMOD RDS Availability [?]
| Himalayan | reference      | extent | (ICIMOD) |     |     |
| --------- | -------------- | ------ | -------- | --- | --- |
| checks    | polygons exist |        |          |     |     |
(ICIMOD 2017,
Rasuwa 2025)
What labels mean. Kuro Siwo marks flood water and permanent water. Our target for the
PS question "where did the flood hit" is the union of model flood water and the rule-based
disturbance layer, so the model's measured metrics describe the water part only; the
report says so.
Leakage control
Use Kuro Siwo's official train/test events; validation by whole event, never random
patches.
Drop any Kuro Siwo event within ~100 km of the Trishuli corridor from training.
Normalisation statistics and thresholds come only from training/validation events.
Nothing from Trishuli (imagery, orbit, labels) enters training or tuning; EMSR927 files
| live in    |  and are read only by  |     |       | .   |     |
| ---------- | ---------------------- | --- | ----- | --- | --- |
| reference/ |                        |     | eval/ |     |     |
Immediately available: Kuro Siwo subset (after size check), GLO-30, ohsome. Needs
action: CDSE account, scene downloads, organisers' answers on the open questions
listed at the end of this document.
Download plan [D]: stratify a Kuro Siwo subset by event and flood fraction (target ~10–
15k training patches); store float16 to fit a free Colab disk. Full float32 is far larger (8
channels × 224² × 4 B ≈ 1.6 MB per patch before compression, my arithmetic), so check
Page 15 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
the real size first.
10. Model and baselines
Primary [D]: U-Net, ResNet-34 encoder, trained on Kuro Siwo with 7 input channels: pre-
mean VV/VH, post VV/VH, post-minus-pre VV/VH, slope. Raw DEM is excluded (elevation
range shifts across regions); HAND is used in post-processing only (it is meaningless
inside a 2.2 km patch).
Why this one: the repo already supports --method unet --backbone resnet18 --dem -
-slope [V]; U-Net-family models are reproducible baselines and architecture differences
were small in one benchmark [S], so data representation and evaluation matter more than
a bigger model.
Item Choice [D]
Init ImageNet encoder, first conv averaged to 7
channels; or scratch if that is worse on validation
Output 3 logits: no water / permanent water / flood
Loss Class-weighted cross-entropy + Dice on flood
class
Optimiser AdamW, lr 3e-4, cosine decay, mixed precision
Batch / patch 32 / 224×224
Sampling ~50% patches containing flood
Augmentation Radiometric (gain shift, speckle noise); no
geometric by default, flips tested in ablation
(geometric augmentation hurt in one benchmark
[S]; flips alter look geometry)
Schedule ≤30 epochs on the subset, checkpoint every
epoch, early stop on validation-event flood IoU
Threshold Flood threshold tuned on validation events only;
also report PR curves
Calibration Temperature scaling on validation events; report
ECE
Page 16 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Item Choice [D]
Reproducibility Fixed seeds (1 minimum, 3 if time), pinned env,
config snapshots
Compute Free Colab T4 for training; CPU is enough for
inference on small AOIs (my estimate, measure it)
Baselines
| ID Baseline |     | Purpose |
| ----------- | --- | ------- |
B0 Change threshold (Otsu/robust) + permanent- Non-learned reference
water removal + HAND mask
B1 Released Kuro Siwo SNUNet weights, zero-shot Published reference
(check input format first)
| B2 U-Net, post-only                              |     | Tests H1   |
| ------------------------------------------------ | --- | ---------- |
| B3 U-Net, pre+post+difference                    |     | Core model |
| P B3 + slope input + gating (+ S2 corroboration) |     | Proposed   |
If P beats B3 on aggregate but loses on steep slopes, the conclusion is restricted
accordingly (section 11).
11. Experimental and evaluation protocol
Metrics, in plain language
| Metric | Meaning                  | Why included                  |
| ------ | ------------------------ | ----------------------------- |
| IoU    | Overlap of predicted and | Standard, harsh on boundaries |
reference flood divided by
their union
Precision Of pixels we call flood, how False alarms waste rescue
|        | many truly are            | effort                   |
| ------ | ------------------------- | ------------------------ |
| Recall | Of true flood pixels, how | Misses are the dangerous |
|        | many we found             | error                    |
Page 17 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Metric    | Meaning                  |     | Why included             |     |
| --------- | ------------------------ | --- | ------------------------ | --- |
| F1 / Dice | Balance of precision and |     | Single comparable number |     |
recall
| Stable-steep FPR | Share of pixels with HAND   |     | Direct measure of            |     |
| ---------------- | --------------------------- | --- | ---------------------------- | --- |
|                  | >100 m and slope >20°       |     | shadow/layover false alarms, |     |
|                  | (cannot be flooded) flagged |     | needs no EMS data            |     |
as flood
Boundary F1 (30 m Edge agreement allowing for Fair to SAR resolution
| tolerance) | 10 m pixels vs VHR-derived |     |     |     |
| ---------- | -------------------------- | --- | --- | --- |
reference
Per-event and per-slope- Metrics split by event and by Pooled averages hide terrain
| stratum scores | slope bin (0–5°, 5–15°, >15°) |     | failures                     |     |
| -------------- | ----------------------------- | --- | ---------------------------- | --- |
| ECE            | Gap between stated            |     | Tests whether the confidence |     |
|                | confidence and observed       |     | map can be trusted           |     |
accuracy
Closed-edge Our closed roads/bridges vs Closest available check for
| precision/recall | EMS-damaged transport |     | cut-off logic |     |
| ---------------- | --------------------- | --- | ------------- | --- |
features (25 m match)
| Runtime, peak RAM | Wall time and memory per |     | Live judging |     |
| ----------------- | ------------------------ | --- | ------------ | --- |
AOI size
Experiments
| ID Question | Data | Compared |     | Output |
| ----------- | ---- | -------- | --- | ------ |
E1 How good is each Kuro Siwo official B0, B1, B2, B3, P Per-event table +
| model on held-out | test events |     |     | pooled |
| ----------------- | ----------- | --- | --- | ------ |
events?
| E2 Does terrain | E1 patches      | Same |     | Slope-stratified |
| --------------- | --------------- | ---- | --- | ---------------- |
| change the      | binned by slope |      |     | table            |
| result?         | band            |      |     |                  |
Page 18 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| ID Question | Data | Compared | Output |
| ----------- | ---- | -------- | ------ |
E3 Which Validation + test Ablations: post- Ablation table with
| component | events | only, +pre,          | seeds |
| --------- | ------ | -------------------- | ----- |
| helps?    |        | +difference, +slope, |       |
+gating,
with/without flips,
loss variants
E4 Does it transfer to Trishuli, P vs B0 vs B1 Pixel + boundary +
| the Himalaya,   | EMSR927 as |     | object agreement, |
| --------------- | ---------- | --- | ----------------- |
| with no tuning? | reference  |     | per AOI, plus a   |
disagreement
taxonomy (cloud,
geometry, DEM,
OSM, definition
mismatch)
| E5 Does same-track | One Trishuli AOI, | P   | Stable-steep FPR, |
| ------------------ | ----------------- | --- | ----------------- |
| matter?            | same-track vs a   |     | both pairings     |
cross-track pre
scene
E6 How robust is the OSM graph (i) synthetic-graph Table of status
| cut-off result? |     | unit tests; (ii)    | changes and flip |
| --------------- | --- | ------------------- | ---------------- |
|                 |     | closure replay with | rate             |
EMS-damaged
features; (iii) three
scenarios; (iv) 20
random 10% and
20% road-edge
dropouts
E7 Is it fast enough 10, 20, 40 km Pipeline end to end Time + RAM table
| live? | AOIs |     |     |
| ----- | ---- | --- | --- |
E8 Is confidence Validation events Before/after ECE overall and per
| calibrated? |     | temperature | slope bin |
| ----------- | --- | ----------- | --------- |
scaling
Targets set before training [D] (they may fail; we report either way)
E1: P flood IoU at least 10 pts above B0; B3 within about 5 F1 pts of the published figure
for comparable models on the same events [verify the figure in the full paper].
Page 19 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
E2/H2: false-positive area on slope >15° reduced ≥30% with ≤5 pts recall loss.
E4: no numeric target; the deliverable is an honest table. I will not promise an IoU.
E7: ≤20 min for a 20×20 km AOI on a 16 GB laptop [unmeasured target].
Minimum to submit: E1, E4, E6(i) and E6(iii).
Interpretation rules
Better pooled IoU but worse on slope >15° → claim only for flatter terrain and say so; do
not average it away.
Good Kuro Siwo score but poor Trishuli score → report domain shift, show the failure
classes, do not retune on EMSR927.
EMS disagreement is not automatically our error: the product is analyst-made from
VHR optical imagery, may include different classes, and may be from a different date.
Exposure counts are "exposed", damage is never inferred from a 10 m SAR cue alone.
12. Technology stack
| Tool | Purpose | Alternatives | Free? | Verdict |
| ---- | ------- | ------------ | ----- | ------- |
considered
| Python 3.11, uv or conda    | Everything     | —                   | Yes | Required    |
| --------------------------- | -------------- | ------------------- | --- | ----------- |
| PyTorch +                   | U-Net training | Plain PyTorch; Kuro | Yes | Reuse repo  |
| segmentation_models_pytorch |                | Siwo trainer        |     | loader, own |
| (or Kuro Siwo repo code)    |                |                     |     | wrapper for |
extra
channels
| ESA SNAP + GPT       | S1                  | sarsen, pyroSAR,    | Yes    | Primary for  |
| -------------------- | ------------------- | ------------------- | ------ | ------------ |
|                      | radiometric/terrain | Sentinel Hub        |        | model        |
|                      | processing          | orthorectification, |        | consistency; |
|                      | matching Kuro Siwo  | ASF HyP3            |        | heavy (RAM)  |
| Sentinel Hub on CDSE | Fast-mode           | HyP3 queue          | Free   | Fallback;    |
| (optional)           | orthorectified S1   |                     | quota, | domain       |
|                      |                     |                     | limits | mismatch     |
|                      |                     |                     | [?]    | must be      |
measured;
ask
organisers
whether it
counts as
"raw"
Page 20 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Tool | Purpose | Alternatives | Free? | Verdict |
| ---- | ------- | ------------ | ----- | ------- |
considered
| pystac-client + requests | CDSE            | OData only | Free    | Required; |
| ------------------------ | --------------- | ---------- | ------- | --------- |
|                          | search/download |            | account | verify    |
endpoint
rasterio, rioxarray, geopandas, Raster/vector work GDAL CLI Yes Required
shapely, pyproj
| pyflwdir | HAND, flow           | whitebox, pysheds, | Yes | Chosen;        |
| -------- | -------------------- | ------------------ | --- | -------------- |
|          | direction, flow path | richdem            |     | verify API [?] |
| NetworkX | Graph and multi-     | igraph,            | Yes | Enough for ≤   |
|          | source Dijkstra      | OpenRouteService   |     | a few 100k     |
edges
ohsome REST OSM snapshot by Overpass attic date Yes Required by
|     | date |     |     | PS; Overpass |
| --- | ---- | --- | --- | ------------ |
only if
organisers
allow
Streamlit + leafmap/folium Map dashboard FastAPI + Yes Chosen:
|     |     | Leaflet/MapLibre |     | Python-only, |
| --- | --- | ---------------- | --- | ------------ |
fastest to
build
| Jinja2 + WeasyPrint    | One-page PDF from | ReportLab | Yes  | Template      |
| ---------------------- | ----------------- | --------- | ---- | ------------- |
|                        | JSON              |           |      | only; no LLM  |
| pytest, GitHub Actions | Tests             | —         | Yes  | Required for  |
| (optional)             |                   |           |      | leakage test  |
| Colab free (T4)        | Training          | Local GPU | Free | Sufficient    |
|                        |                   |           | with | with a subset |
usage
limits
Deliberately not used: Google Earth Engine (extra account/quota, hides preprocessing),
foundation models, DVC, Docker orchestration, a separate backend service.
Page 21 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
13. Repository structure
cutoff/
README.md ATTRIBUTION.md LICENSE environment.yml Makefile
configs/ default.yaml paths.yaml train_unet.yaml
closure_scenarios.yaml
src/cutoff/
data/ cdse.py s1_pairs.py s1_preprocess.py dem.py osm.py s2.py
kuro_siwo.py
geo/ terrain.py change.py gating.py vectorize.py exposure.py
network.py flowpath.py
ml/ dataset.py model.py train.py infer.py calibrate.py
report/ schema.py build_report.py sitrep.html.j2
pipeline.py cli.py
eval/ metrics.py splits.py baselines.py ablations.py
emsr927.py cutoff_eval.py
app/ streamlit_app.py
graphs/ s1_kuro_siwo.xml (copied from Kuro Siwo configs, with
attribution)
scripts/ download_kuro_siwo.sh fetch_dem.sh run_trishuli.sh
tests/ test_pairs.py test_network.py test_gating.py
test_no_reference_leak.py
notebooks/ colab_train.ipynb
docs/ limitations.md data_rules_audit.md report/
reference/ (git-ignored; EMSR927 files, read only by eval/)
outputs/ (git-ignored; runs and checkpoints)
File Responsibility Inputs → outputs Depends on Ours or
adapted
data/s1_pairs.py Pick same-track pair; reject cross- AOI, date → cdse.py Ours
track pairs.json
data/s1_preprocess.py Run SNAP graph on subset, write GRD, DEM → tifs graphs/*.xml Ours around
dB COGs + shadow mask Kuro Siwo
graph
data/dem.py Download/mosaic GLO-30 AOI → dem.tif — Ours
data/osm.py ohsome calls (tiled), assert date < AOI, date → gpkg — Ours
2026-08-26
data/s2.py L2A + SCL clear mask, pre AOI, dates → tifs cdse.py Ours (optional)
composite
data/kuro_siwo.py Event table, subset sampler, repo/HF → index — Adapted
slope-strata index
geo/terrain.py Slope, aspect, HAND, flow-dir dem.tif → rasters pyflwdir Ours
Page 22 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| File | Responsibility | Inputs → outputs | Depends on | Ours or |
| ---- | -------------- | ---------------- | ---------- | ------- |
adapted
geo/change.py Pre-mean, difference, S1 stack, HAND → terrain.py Ours
|     | sigma_stable, disturbance mask | masks |     |     |
| --- | ------------------------------ | ----- | --- | --- |
geo/gating.py Shadow/layover/slope/HAND prob + masks → change.py Ours
|     | downgrade, S2 corroboration, | classes |     |     |
| --- | ---------------------------- | ------- | --- | --- |
confidence tier
geo/vectorize.py Raster→polygons with attributes rasters → rasterio Ours
hazard.gpkg
geo/exposure.py Hazard ∩ buildings/roads/bridges gpkgs → counts vectorize.py Ours
by tier
geo/network.py Graph build (split at shared roads, places, NetworkX Ours
|     | vertices), scenarios, statuses | hospitals, hazard → |     |     |
| --- | ------------------------------ | ------------------- | --- | --- |
status gpkg
geo/flowpath.py Bonus: path from point, DEM, point → list terrain.py Ours
settlements within corridor
|               | Kuro Siwo wrapper adding | index → tensors |              | Ours |
| ------------- | ------------------------ | --------------- | ------------ | ---- |
| ml/dataset.py |                          |                 | kuro_siwo.py |      |
difference channels
ml/model.py, train.py, infer.py U-Net, training loop, tiled tensors → PyTorch Ours using
|     | inference | checkpoints, |     | library  |
| --- | --------- | ------------ | --- | -------- |
|     |           | p_flood.tif  |     | encoders |
ml/calibrate.py Temperature scaling, ECE val logits → T — Ours
| report/schema.py | Pydantic schema of | —   | —   | Ours |
| ---------------- | ------------------ | --- | --- | ---- |
results.json (every reported
number)
report/build_report.py + One-page sitrep with attribution JSON → PDF schema.py Ours
| template | footer |     |     |     |
| -------- | ------ | --- | --- | --- |
pipeline.py, cli.py Orchestrate stages 1–8 AOI, date → run all above Ours
folder
eval/emsr927.py Rasterise/compare EMSR927 reference/, run metrics.py Ours, never
|     | layers | outputs → tables |     | imported by |
| --- | ------ | ---------------- | --- | ----------- |
pipeline
eval/cutoff_eval.py Closure replay, OSM dropout graph + EMS network.py Ours
closures → table
|     | Fails if pipeline imports | source scan | —   | Ours |
| --- | ------------------------- | ----------- | --- | ---- |
tests/test_no_reference_leak.py
eval/reads reference/, or OSM
date ≥ 2026-08-26
app/streamlit_app.py AOI/date form, run, layers, run folder → UI pipeline.py Ours
scenario toggle, evidence panel,
sitrep download
Do not vendor the whole Kuro Siwo repo; import its loader code with attribution or copy
the preprocessing XML and cite it.
Page 23 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
14. Sequential implementation roadmap
Suggested split for up to four people: ML (M5–M8, M10); SAR/terrain (M3, M4, M9);
OSM/network/exposure (M11, tests); app/report/video (M12, M15–M16). If solo, follow the
critical path and drop the bonus and S2.
# Milestone (days) Tasks and files Done when Likely errors and
fixes
M1 Requirement Fix section 2 matrix, Matrix signed Scope creep:
| freeze (D1) | assumptions,  |     | off | anything not in  |
| ----------- | ------------- | --- | --- | ---------------- |
|             | questions for |     |     | the matrix waits |
organisers
| M2 Environment and | Repo, |     | Fresh clone | GDAL/rasterio |
| ------------------ | ----- | --- | ----------- | ------------- |
| repo (D1)          |       |     | , runs      | wheels: use   |
environment.yml make
|     | Makefile | , CI optional, | test | conda-forge |
| --- | -------- | -------------- | ---- | ----------- |
ATTRIBUTION.md
| M3 Data acquisition | CDSE account; |            | Files +    | Slow/failed |
| ------------------- | ------------- | ---------- | ---------- | ----------- |
| (D1–3)              |               | ; download | checksums; | downloads:  |
cdse.py
|     | Trishuli same-track set; |     | Kuro Siwo event | resume, pre-      |
| --- | ------------------------ | --- | --------------- | ----------------- |
|     | GLO-30; Kuro Siwo size   |     | table           | download          |
|     | check then subset;       |     |                 | overnight; ohsome |
|     | ohsome 2026-07-27        |     |                 | limits: tile bbox |
M4 S1 preprocessing Read Kuro Siwo XML Trishuli pre/post SNAP out-of-
| (D2–4) | (units, DEM, filter); |     | dB rasters align    | memory: subset   |
| ------ | --------------------- | --- | ------------------- | ---------------- |
|        | s1_preprocess.py      |     | ; on stable terrain | first, raise JVM |
|        | subset before heavy   |     |                     | heap; unit       |
|        | steps                 |     |                     | mismatch with    |
Kuro Siwo: match
its graph
| M5 Dataset | kuro_siwo.py |     | , plot 20 patches | Misaligned |
| ---------- | ------------ | --- | ----------------- | ---------- |
validation (D3–4) patches, label sanity, inspected; channels: assert
|     | slope-strata index |     | strata counts | shapes and CRS |
| --- | ------------------ | --- | ------------- | -------------- |
M6 Baselines (D4–5) baselines.py  B0, B1 E1 numbers for B1 weight format:
B0/B1 read repo loader
Page 24 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
# Milestone (days) Tasks and files Done when Likely errors and
fixes
| M7 Training (D5–8) | train.py        | ,   | Checkpoint + | Colab            |
| ------------------ | --------------- | --- | ------------ | ---------------- |
|                    | train_unet.yaml | ,   | validation   | disconnects:     |
|                    | Colab notebook  |     | curves       | checkpoint every |
epoch; overfit:
early stop by
event
M8 Evaluation and metrics.py , E1, E2, E8, Tables + 10 Pooled metric
| error analysis | error gallery |            | failure examples | hides strata:    |
| -------------- | ------------- | ---------- | ---------------- | ---------------- |
| (D8–9)         |               |            |                  | always stratify  |
| M9 Core        | terrain.py    | ,          | Gated masks on   | No threshold     |
| contribution   | change.py     | ,          | Trishuli         | tuning on        |
| (D6–9)         | gating.py     | , optional |                  | EMSR927; fix k=3 |
|                | s2.py         |            |                  | first            |
M10 Ablations and ablations.py , E3, E5 Ablation + Seed noise: ≥3
| comparison (D9– |             |     | same/cross-  | seeds where  |
| --------------- | ----------- | --- | ------------ | ------------ |
| 11)             |             |     | track tables | affordable   |
| M11 Geospatial  | exposure.py | ,   | Statuses for | OSM topology |
inference (D6–11) network.py , Trishuli; E6 gaps: split ways at
|     | flowpath.py           | ; build |     | shared vertices; |
| --- | --------------------- | ------- | --- | ---------------- |
|     | and test on synthetic |         |     | unsnapped        |
|     | hazards from D6       |         |     | villages →       |
"unknown"
| M12 Backend and   | schema.py | ,   | UI works on    | Heavy rasters in |
| ----------------- | --------- | --- | -------------- | ---------------- |
| interface (D9–12) |           |     | mock then real | browser: serve   |
streamlit_app.py
|     | against mock |        | run | PNG/COG  |
| --- | ------------ | ------ | --- | -------- |
|     | results.json |  first |     | overlays |
M13 Integration (D12– pipeline.py , caching, One command Stage contract
| 13) | timing |     | runs two AOIs | drift: schema |
| --- | ------ | --- | ------------- | ------------- |
tests
M14 Testing and Four tests, fresh-clone Teammate Hidden local
reproducibility run, seeds, README reproduces in a paths: grep and fix
| (D13–14) |     |     | clean env |     |
| -------- | --- | --- | --------- | --- |
Page 25 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
# Milestone (days) Tasks and files Done when Likely errors and
fixes
M15 Deployment and Rehearse live run on a Video ≤3:00 Network failure:
demo (D14–15) non-Trishuli AOI; record cached scenes
video
M16 Final Report ≤6 pages, Page count and Overlong report:
documentation limitations, pitch, checklist met move tables to
(D12–15) citations appendix files
Critical path: M3 → M4 → M7 → M8 → M10 → M13 → M15. M4 is the riskiest link. M11 and
M12 run in parallel on mock data from day 6, so integration is not left to the end.
Pipeline sketches (verify endpoints before relying on them)
# OSM snapshot via ohsome (tile large bboxes)
curl -s -X POST https://api.ohsome.org/v1/elements/geometry \
-d "bboxes=W,S,E,N" -d "time=2026-07-27" \
-d "filter=highway=* and geometry:line" -d "properties=tags" >
roads.geojson
# Same-track selection (endpoint and field names to verify on CDSE)
from pystac_client import Client
cat = Client.open("https://stac.dataspace.copernicus.eu/v1")
items = list(cat.search(collections=["sentinel-1-grd"], bbox=aoi,
datetime="2026-07-15/2026-09-10").items())
# group by relative orbit + direction; need 1 post and >=1 pre at -12/-24/-36
d; else "no valid observation"
# Cut-off status under one closure scenario
d0 = nx.multi_source_dijkstra_path_length(G, dests, weight="t") #
baseline
H = G.copy(); H.remove_edges_from(closed) #
scenario
d1 = nx.multi_source_dijkstra_path_length(H, dests, weight="t")
for s in settlements:
if s not in d0: status[s] = "unknown" # no baseline route in OSM
elif s not in d1: status[s] = "cut_off"
elif d1[s] > 1.5 * d0[s]: status[s] = "degraded" # 1.5x is a declared
choice
else: status[s] = "connected"
Page 26 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Closure scenarios [D]: S-A conservative (any intersection with hazard probability ≥ 0.5, 15
m tolerance for 10 m pixels and OSM positional error); S-B moderate (≥50 m of road inside
high-confidence hazard); S-C bridges only. The report shows the range S-C to S-A, not a
single number.
15. Hardware, software, time and cost estimates
| Item | Estimate |     |     | Basis |     |
| ---- | -------- | --- | --- | ----- | --- |
Laptop 16 GB RAM, ~150 GB free disk SNAP is memory-hungry; S1 GRD scenes
are large [unmeasured]
GPU Free Colab T4, roughly 4–8 GPU My estimate for a ~10–15k patch subset;
|           | hours total                     |     |     | measure in M7                  |     |
| --------- | ------------------------------- | --- | --- | ------------------------------ | --- |
| Inference | CPU, tiled                      |     |     | Small AOIs only; measure in E7 |     |
| Software  | All free/open source            |     |     | Table in section 12            |     |
| Cash      | ~$0 base; optional Colab Pro if |     |     | Quotas may change              |     |
sessions are cut
| Calendar | 15 days; critical path ~11 days of |     |     | Section 14 |     |
| -------- | ---------------------------------- | --- | --- | ---------- | --- |
serial work
16. Risk register and fallbacks
| Risk |     | L I | Mitigation |     | Fallback |
| ---- | --- | --- | ---------- | --- | -------- |
preserving the PS
Kuro Siwo download M H Size check first; webdataset Train on a smaller
| too large/slow |     |     | subset |     | subset or use B1 |
| -------------- | --- | --- | ------ | --- | ---------------- |
only
| No debris labels |     | H M | Rule-based disturbance |     | Water-only claim |
| ---------------- | --- | --- | ---------------------- | --- | ---------------- |
layer, clearly labelled
| CRS/coordinate |     | M M | UTM zone from AOI       |     | Reproject at stage |
| -------------- | --- | --- | ----------------------- | --- | ------------------ |
| mismatch       |     |     | centroid; assert CRS on |     | boundary           |
every raster
Page 27 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
| Risk | L I | Mitigation |     | Fallback |
| ---- | --- | ---------- | --- | -------- |
preserving the PS
| Misregistration | M M | Same-track only; check        |     | Phase-correlation |
| --------------- | --- | ----------------------------- | --- | ----------------- |
|                 |     | correlation on stable terrain |     | shift             |
Class imbalance H M Weighted loss, flood-biased Report per-class
|            |     | sampling                |     | metrics          |
| ---------- | --- | ----------------------- | --- | ---------------- |
| GPU limits | M M | Subset, ResNet-18, fp16 |     | B0 + B1 pipeline |
still delivers all PS
questions
Poor steep-terrain H H Gating; slope-stratified State the limit in
| performance     |     | honesty                    |     | the report        |
| --------------- | --- | -------------------------- | --- | ----------------- |
| Domain shift to | H H | Adaptive thresholds; zero- |     | Present as        |
| Himalaya        |     | tuning report              |     | measured transfer |
gap
| Preprocessing too | H H | Subset first; cache; |     | Show cached run |
| ----------------- | --- | -------------------- | --- | --------------- |
slow for live demo precomputed Trishuli; fast plus live small AOI
mode
| CDSE outage or     | M H | Pre-downloaded scenes |     | Sentinel Hub fast |
| ------------------ | --- | --------------------- | --- | ----------------- |
| quota              |     |                       |     | path              |
| No same-track post | M H | Explicit "no valid    |     | Cross-track       |
scene for judge AOI observation" and next-pass ablation, flagged
|          |     | date                      |     | not comparable |
| -------- | --- | ------------------------- | --- | -------------- |
| OSM gaps | H M | "Unknown" status; dropout |     | Report ranges  |
study
| Integration | M H | results.json      |  contract and | Ship CLI + static |
| ----------- | --- | ----------------- | ------------- | ----------------- |
| incomplete  |     | mock data from D6 |               | report            |
Rule violation via L Critical Folder separation, leakage Remove the
| leakage |     | test, review |     | dependency |
| ------- | --- | ------------ | --- | ---------- |
before submission
| Novelty claim fails | M L | Claims limited to      |     | Reword |
| ------------------- | --- | ---------------------- | --- | ------ |
| prior-art check     |     | engineering/evaluation |     |        |
Three levels
Page 28 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Minimum viable: same-track pairing, U-Net B3 + basic gating, exposure, one closure
scenario with four statuses, Streamlit map, template sitrep, E1 + E4 + E6(i)(iii), tests,
README, report, video.
Strong: E2–E8, three scenarios, OSM dropout study, S2 corroboration, temperature
scaling, bonus flow path, EMS closure replay.
Advanced (only if ahead): Nepali template strings reviewed by a native speaker,
conformal abstain class, a second Himalayan check scene (if reference polygons exist),
SLC coherence.
17. Final demonstration scenario (3 minutes)
Time Content
0:00–0:20 The question rescuers ask; one-line disclaimer
(educational prototype); no victim imagery
0:20–1:20 Enter Trishuli AOI + 26 Aug: same-track pair shown,
hazard layers appear, evidence/confidence toggle
1:20–2:00 EMSR927 comparison panel: agreement,
disagreement reasons, stratified metrics, failure
panel
2:00–2:30 Exposure counts and cut-off table with scenario
toggle; "unknown" settlements explained
2:30–3:00 One-page sitrep, limitations in one sentence each,
attributions
Rehearse a live run on a non-Trishuli AOI so the answer to "does it work anywhere?" is
shown, not asserted.
18. Judging pitch
Problem: after a debris flood, rescuers need to know where the valley changed and
who lost road access, from satellites, quickly.
Existing gap: flood masks, flooded-road overlays and healthcare-access analyses exist
separately; Himalayan terrain false alarms and the link from hazard to isolation are
rarely tested under held-out conditions.
Page 29 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Solution: Cutoff runs same-track Sentinel-1 change detection with terrain gating and a
trained model, then a scenario-based road-graph analysis.
Contribution: engineering and evaluation, not a new architecture: automated pairing,
gating, slope-stratified held-out tests, Trishuli check with zero tuning, cut-off
sensitivity.
Evidence: (fill with measured E1, E2, E4, E6 numbers; none exist yet).
Impact: a transparent, reproducible starting point; ranges and "unknown" instead of
false certainty.
Limitations: revisit gaps, 10 m pixels, smooth mud vs water, OSM gaps, exposure is not
damage, educational prototype only.
19. References
Verified this session ([V]) unless marked.
Official PS: Track_B.pdf / Space_Track.pdf (supplied).
Kuro Siwo repo: https://github.com/Orion-AI-Lab/KuroSiwo [V]; paper: Bountos et al.,
NeurIPS 37 (2024), pp. 38105–38121, https://arxiv.org/abs/2311.12056 and
https://proceedings.neurips.cc/paper_files/paper/2024/hash/43612b0662cb6a4986edf
859fd6ebafe-Abstract-Datasets_and_Benchmarks_Track.html [V]; data:
https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-Webdataset and
https://huggingface.co/datasets/orion-ai-lab/Kuro-Siwo-GeoTIFFs [V].
Sen1Floods11: https://github.com/cloudtostreet/Sen1Floods11; doi
10.1109/CVPRW50498.2020.00113 [S].
GEOID-Flood: https://arxiv.org/pdf/2608.02315; https://github.com/links-ads/geoid-
flood [V].
MMFlood: https://github.com/edornd/mmflood [V].
EMSR927: https://mapping.emergency.copernicus.eu/news/flood-in-nepal-emsr927/
[V]; EU Space image pages: https://eu-space.europa.eu/components/earth-
observation-copernicus/image-of-the-day/aftermath-nepal-flash-flood and https://eu-
space.europa.eu/components/earth-observation-copernicus/image-of-the-
day/copernicus-emergency-management-service-maps-flood-damages-northern-
nepal [V].
Event summary (secondary): https://gee-community-
catalog.org/projects/nepal_floods_2026/ [V].
Page 30 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
ICIMOD 2017 Nepal flood extent: https://rds.icimod.org/metadata/8d97f509-a256-
4e80-bf39-223b534a73fa [V]; NDRRMA 2025 sitrep: https://dpnet.org.np/resource-
detail/2197 [V].
ohsome API: https://docs.ohsome.org/ohsome-api/stable/ [V].
Via Elicit/Docs A–C only [S]: Petricola et al. 2022 https://doi.org/10.1186/s12942-022-
00315-2; Helleis et al. 2022 https://doi.org/10.1109/jstars.2022.3152127; Yang et al. 2021
https://doi.org/10.3390/rs13112205; github.com/GIScience/healthcare-access-idai;
github.com/JakubNiedzwiedz/SAR-Flood-Detection; github.com/AliForghani/sentinel1-
sar-flood-mapping.
Required attribution strings (copied from the PS; put them in the README, dashboard
footer, report and sitrep):
"Contains modified Copernicus Sentinel data 2026."
"Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus
Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European
Union and ESA; all rights reserved."
"© OpenStreetMap contributors."
Plus the Kuro Siwo citation and, for EMSR927 comparisons, "European Union, Copernicus
Emergency Management Service data".
20. Final checklist
Verified in this session Decided (design) Needs experiment or
confirmation
PS rules, weights, AI component = Kuro Siwo download size and
attribution strings segmentation model event geography
Kuro Siwo: 43 events, Training on Kuro Siwo Contents of
67,490 patches, 2 pre + 1 only grd_preprocessing.xml ; weight
post, DEM/slope, 3 classes, input format
MIT file vs CC BY text,
trainer flags, released
weights
GEOID-Flood and MMFlood Reject EMS-derived Same-track S1 availability and
are EMS-derived training sets latency for the corridor
Page 31 of 32

Cutoff — Track B project blueprint (Himalayan flood, debris & access mapping)
Verified in this session Decided (design) Needs experiment or
confirmation
EMSR927 scope; four AOIs; U-Net B3 + slope + EMSR927 vector layers and
>240 destroyed / 32 gating; temperature legend; whether EMS lists
damaged in one AOI view scaling damaged roads/bridges
S2 scenes of 12 and 27 Aug Closure scenarios S-A/S- Every hypothesis H1–H6
exist near B/S-C; four statuses; 1.5×
Betrawati/Gerkhu degraded rule
Event timing and Scene-adaptive pyflwdir API; Sentinel Hub quota;
provisional-damage thresholds, k=3, HAND ohsome response limits
caveats from the corridor start 60 m
community catalog
ohsome supports time Streamlit dashboard; Whether any second Himalayan
and filter template report, no LLM check scene has reference
polygons
Questions to put to the organisers before building around them
1. Will the live round allow pre-downloaded scenes and cached runs, and is there reliable
internet for CDSE downloads?
2. Does Sentinel Hub (on CDSE) orthorectified Sentinel-1 count as "raw satellite data", or
must preprocessing run locally?
3. Are high-resolution open images (Planet/Maxar, CC BY-NC) acceptable for visual
checking only, or should they be avoided entirely?
4. Is a Nepali report expected under the segmentation option, or only under the copilot
option?
Page 32 of 32
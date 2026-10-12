"""Frozen cross-team contracts (Phase 0, contract v1.0.0).

Everything the four work streams exchange is defined here: model channels, hazard
class codes, evidence flags, access statuses, closure scenarios, and the run-folder
file layout. Changing anything in this file is a "contract change": it needs a PR
labelled `contract-change` approved by all four owners (docs/plan/05_contracts.md).
"""
from __future__ import annotations

from enum import IntEnum

CONTRACT_VERSION = "1.0.0"

# --------------------------------------------------------------------------- dates
# PS data rule: OSM must be the state BEFORE the event. Latest snapshot named in the PS.
DEFAULT_OSM_SNAPSHOT = "2026-07-27T00:00:00Z"
TRISHULI_EVENT_UTC = "2026-08-26T02:52:00Z"  # gee-community-catalog (seismic onset 02:52-02:55 UTC)

# --------------------------------------------------------------------------- SAR / model
DB_FLOOR = -30.0
DB_CEIL = 5.0
SLOPE_CLIP_DEG = (0.0, 15.0)  # D6: Kuro Siwo is lowland-heavy; steeper slopes are out-of-distribution
CHANNELS = ("vv_pre_db", "vh_pre_db", "vv_post_db", "vh_post_db", "dvv_db", "dvh_db", "slope_deg")
N_CHANNELS = len(CHANNELS)
MODEL_CLASSES = ("no_water", "permanent_water", "flood")  # Kuro Siwo mask 0/1/2
IGNORE_INDEX = 255
PIXEL_M = 10.0


class HazardClass(IntEnum):
    """Values of hazard_class.tif (uint8)."""

    NONE = 0
    FLOOD_HIGH = 1          # model flood, plausible terrain (or S2-confirmed)
    FLOOD_POSSIBLE = 2      # model flood on steep / high-HAND terrain, or contradicted by clear S2
    RULE_DECREASE = 3       # same-track backscatter drop in valley corridor: water / smooth mud
    RULE_INCREASE = 4       # same-track backscatter rise in valley corridor: roughness / debris
    PERMANENT_WATER = 5     # model permanent-water class
    NO_OBS = 254            # radar shadow / layover / no data


HAZARD_CLASS_NAMES = {c.value: c.name.lower() for c in HazardClass}
# Classes that answer "where did the flood hit?" (used by exposure, scenario A, check-only evaluation)
HAZARD_CLASSES = (HazardClass.FLOOD_HIGH, HazardClass.FLOOD_POSSIBLE,
                  HazardClass.RULE_DECREASE, HazardClass.RULE_INCREASE)
# High-confidence classes (scenarios B and C)
HIGH_CONFIDENCE_CLASSES = (HazardClass.FLOOD_HIGH, HazardClass.RULE_INCREASE)


class Flag(IntEnum):
    """Bits of flags.tif (uint8): why a pixel got its class."""

    MODEL_FLOOD = 1
    RULE_DECREASE = 2
    RULE_INCREASE = 4
    S2_WATER_AGREE = 8
    S2_CLEAR_NO_WATER = 16
    STEEP = 32
    HIGH_HAND = 64
    SHADOW_LAYOVER = 128


class Disturbance(IntEnum):
    """Values of disturb.tif (int8)."""

    INVALID = -1
    NONE = 0
    DECREASE = 1
    INCREASE = 2


ACCESS_STATUSES = ("connected", "degraded", "cut_off", "unknown")
SCENARIOS = {
    "A": "Conservative: any road piece within 15 m of any hazard class 1-4 is closed",
    "B": "Moderate: road piece closed if >= 50 m of it lies in high-confidence hazard (1, 4)",
    "C": "Bridges only: bridge closed if high-confidence hazard reaches its approaches",
}

S1_BACKENDS = ("sentinelhub", "snap", "cached")
RUN_MODES = ("cached", "fast", "full")  # fast -> sentinelhub backend, full -> snap backend

# --------------------------------------------------------------------------- run folder
# Every stage reads and writes ONLY these files inside outputs/<run_id>/.
# Rasters: GeoTIFF on the run's analysis grid (grid.json): same CRS (UTM), transform, shape.
RASTERS = {
    # key: (filename, bands, dtype, nodata, owner)
    "s1_pre_mean": ("s1_pre_mean.tif", 2, "float32", "nan", "P1"),   # linear sigma0 VV,VH, mean of pre scenes
    "s1_post": ("s1_post.tif", 2, "float32", "nan", "P1"),           # linear sigma0 VV,VH
    "lia": ("lia.tif", 1, "float32", "nan", "P1"),                   # local incidence angle, degrees
    "shadow_layover": ("shadow_layover.tif", 1, "uint8", None, "P1"),  # 1 = unobservable
    "dem": ("dem.tif", 1, "float32", "nan", "P1"),                   # GLO-30 resampled, metres
    "slope": ("slope.tif", 1, "float32", "nan", "P1"),               # degrees
    "hand": ("hand.tif", 1, "float32", "nan", "P1"),                 # metres above nearest drainage
    "flwdir": ("flwdir_d8.tif", 1, "uint8", 247, "P1"),              # pyflwdir/ESRI D8 codes
    "s2_water": ("s2_water.tif", 1, "uint8", 255, "P1"),             # optional: 1 MNDWI water
    "s2_clear": ("s2_clear.tif", 1, "uint8", 255, "P1"),             # optional: 1 clear (SCL 4,5,6,7; snow excluded)
    "p_model": ("p_model.tif", 3, "float32", "nan", "P2"),           # calibrated probs no_water/permanent/flood
    "disturb": ("disturb.tif", 1, "int8", None, "P2"),               # Disturbance codes
    "hazard_class": ("hazard_class.tif", 1, "uint8", None, "P2"),    # HazardClass codes
    "flags": ("flags.tif", 1, "uint8", None, "P2"),                  # Flag bitfield
}
OPTIONAL_RASTERS = ("s2_water", "s2_clear")

VECTORS = {
    # key: (filename, geometry type, required columns, owner)
    "hazard": ("hazard.gpkg", "Polygon", ("class", "area_m2"), "P2"),
    "osm_roads": ("osm_roads.gpkg", "LineString", ("osm_id", "highway", "tier", "bridge", "name"), "P3"),
    "osm_buildings": ("osm_buildings.gpkg", "Polygon", ("osm_id",), "P3"),
    "osm_places": ("osm_places.gpkg", "Point", ("osm_id", "place", "name"), "P3"),
    "osm_health": ("osm_health.gpkg", "Point", ("osm_id", "kind", "name"), "P3"),
    "settlements": ("settlements.gpkg", "Point", ("sid", "name", "source", "n_buildings"), "P3"),
    "targets": ("targets.gpkg", "Point", ("tid", "name", "kind"), "P3"),
    "exposure_buildings": ("exposure_buildings.gpkg", "Polygon", ("osm_id", "hazard_class"), "P3"),
    "exposure_roads": ("exposure_roads.gpkg", "LineString", ("osm_id", "hazard_class", "length_m"), "P3"),
    "settlements_A": ("settlements_A.gpkg", "Point", ("sid", "name", "status", "t0_min", "t1_min"), "P3"),
    "settlements_B": ("settlements_B.gpkg", "Point", ("sid", "name", "status", "t0_min", "t1_min"), "P3"),
    "settlements_C": ("settlements_C.gpkg", "Point", ("sid", "name", "status", "t0_min", "t1_min"), "P3"),
    "roads_A": ("roads_status_A.gpkg", "LineString", ("seg_id", "closed", "bridge"), "P3"),
    "roads_B": ("roads_status_B.gpkg", "LineString", ("seg_id", "closed", "bridge"), "P3"),
    "roads_C": ("roads_status_C.gpkg", "LineString", ("seg_id", "closed", "bridge"), "P3"),
    "flowpath": ("flowpath.gpkg", "LineString", ("start_lon", "start_lat", "length_km"), "P3"),
}
OPTIONAL_VECTORS = ("flowpath",)

OTHER_FILES = {
    "grid": "grid.json",          # P4 (pipeline) writes first; everyone reads
    "pairs": "pairs.json",        # P1
    "results": "results.json",    # P4 assembles from stage outputs; single source of truth
    "sitrep_html": "sitrep.html",  # P4
    "sitrep_pdf": "sitrep.pdf",   # P4
    "run_log": "run.log",         # JSON lines, every stage
}

# --------------------------------------------------------------------------- attribution
ATTRIBUTION = (
    "Contains modified Copernicus Sentinel data 2026.",
    "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH "
    "2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.",
    "© OpenStreetMap contributors.",
    "Flood model trained on Kuro Siwo (Bountos et al., NeurIPS 2024 Datasets & Benchmarks), CC BY 4.0.",
)
EMS_CREDIT = "European Union, Copernicus Emergency Management Service data"  # eval/ ONLY
DISCLAIMER = "Educational prototype - not an operational tool. Exposure is not confirmed damage."
ODBL_NOTICE = "Contains OpenStreetMap data, ODbL 1.0 - © OpenStreetMap contributors."

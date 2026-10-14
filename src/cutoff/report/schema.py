"""results.json schema - the single source of truth (Phase 0, frozen).

The dashboard and the situation report read ONLY this file (plus map layers for
display). Every number shown to a user must be a field here. The pipeline (P4)
assembles it from the summaries returned by each stage.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator

from cutoff.contracts import (
    ACCESS_STATUSES,
    ATTRIBUTION,
    CONTRACT_VERSION,
    DISCLAIMER,
    HAZARD_CLASS_NAMES,
    RUN_MODES,
    S1_BACKENDS,
    SCENARIOS,
)

_CLASS_NAMES = set(HAZARD_CLASS_NAMES.values())


class S1Scene(BaseModel):
    id: str
    datetime: datetime
    platform: str                      # sentinel-1c | sentinel-1d | ...


class Inputs(BaseModel):
    aoi_bbox: tuple[float, float, float, float]   # W, S, E, N degrees
    grid_epsg: int
    event_datetime: datetime
    osm_snapshot: datetime
    mode: Literal[RUN_MODES]  # type: ignore[valid-type]
    s1_backend: Literal[S1_BACKENDS]  # type: ignore[valid-type]
    rel_orbit: int
    orbit_direction: Literal["ascending", "descending"]
    s1_post: S1Scene
    s1_pre: list[S1Scene] = Field(min_length=1)
    post_lag_hours: float
    s2_scenes: list[str] = []
    s2_clear_fraction: float | None = None

    @field_validator("osm_snapshot")
    @classmethod
    def _pre_event(cls, v, info):
        ev = info.data.get("event_datetime")
        if ev is not None and v >= ev:
            raise ValueError("osm_snapshot must be before the event (PS data rule)")
        return v


class Hazard(BaseModel):
    area_km2_by_class: dict[str, float]
    no_observation_km2: float
    sigma_stable_db: float | None = None
    k_sigma: float
    flood_threshold: float
    temperature: float
    stable_steep_fpr: float | None = None   # share of steep, high-HAND pixels flagged as flood

    @computed_field
    @property
    def total_hazard_km2(self) -> float:
        return round(sum(self.area_km2_by_class.get(name, 0.0) for name in
                         ("flood_high", "flood_possible", "rule_decrease", "rule_increase")), 4)

    @field_validator("area_km2_by_class")
    @classmethod
    def _known_classes(cls, v):
        bad = set(v) - _CLASS_NAMES
        if bad:
            raise ValueError(f"unknown hazard class names {bad}")
        return v


class Exposure(BaseModel):
    buildings_by_class: dict[str, int]
    road_km_by_class: dict[str, float]
    bridges_by_class: dict[str, int]

    @computed_field
    @property
    def total_exposed_buildings(self) -> int:
        return sum(self.buildings_by_class.values())


class SettlementRef(BaseModel):
    sid: str
    name: str
    lon: float
    lat: float
    t0_min: float | None = None


class ScenarioResult(BaseModel):
    scenario: Literal[tuple(SCENARIOS)]  # type: ignore[valid-type]
    description: str
    closed_road_km: float
    closed_bridges: int
    counts: dict[str, int]
    cut_off: list[SettlementRef] = []
    degraded: list[SettlementRef] = []

    @field_validator("counts")
    @classmethod
    def _statuses(cls, v):
        bad = set(v) - set(ACCESS_STATUSES)
        if bad:
            raise ValueError(f"unknown access statuses {bad}")
        return v


class FlowPath(BaseModel):
    start_lon: float
    start_lat: float
    length_km: float
    settlements: list[str]


class Results(BaseModel):
    contract_version: str = CONTRACT_VERSION
    run_id: str
    created_utc: datetime
    model_version: str           # checkpoint name, "b0", or "mock"
    inputs: Inputs
    hazard: Hazard
    exposure: Exposure | None = None          # None if OSM failed (partial run, see warnings)
    access: list[ScenarioResult] = []
    flowpath: FlowPath | None = None
    warnings: list[str] = []
    timings_s: dict[str, float] = {}
    limitations: list[str]
    attribution: list[str] = Field(default_factory=lambda: list(ATTRIBUTION))
    disclaimer: str = DISCLAIMER

    @computed_field
    @property
    def is_partial(self) -> bool:
        return self.exposure is None or not self.access or any("Partial run" in w for w in self.warnings)

    @field_validator("attribution")
    @classmethod
    def _attribution_complete(cls, v):
        missing = [a for a in ATTRIBUTION if a not in v]
        if missing:
            raise ValueError(f"required attribution missing: {missing}")
        return v

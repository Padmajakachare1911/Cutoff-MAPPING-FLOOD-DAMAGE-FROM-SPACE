"""RunContext: the single object every pipeline stage receives (Phase 0, frozen).

A stage is a function `stage(ctx: RunContext) -> dict | None`. It reads inputs from
`ctx.path(<key>)`, writes outputs to `ctx.path(<key>)`, appends human-readable
warnings to `ctx.warnings`, and returns a small dict of summary values that the
pipeline copies into results.json. Stages never call each other.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cutoff.contracts import OTHER_FILES, RASTERS, VECTORS
from cutoff.geo.grid import Grid


@dataclass
class RunContext:
    run_dir: Path
    run_id: str
    aoi_bbox: tuple[float, float, float, float]  # W, S, E, N (EPSG:4326)
    event_datetime: datetime                      # timezone-aware UTC
    osm_snapshot: str                             # ISO timestamp, must be < event
    mode: str                                     # cached | fast | full
    cfg: dict[str, Any]                           # parsed configs/default.yaml
    grid: Grid
    model_path: str | None = None                 # checkpoint path or "b0"
    warnings: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    summaries: dict[str, Any] = field(default_factory=dict)

    def path(self, key: str) -> Path:
        """Absolute path of a contract file, e.g. ctx.path('hazard_class')."""
        if key in RASTERS:
            name = RASTERS[key][0]
        elif key in VECTORS:
            name = VECTORS[key][0]
        elif key in OTHER_FILES:
            name = OTHER_FILES[key]
        else:
            raise KeyError(f"'{key}' is not a contract file (see cutoff/contracts.py)")
        return Path(self.run_dir) / name

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def log(self, stage: str, **fields: Any) -> None:
        """Append one JSON line to run.log (stage progress, timings, warnings)."""
        rec = {"t": time.time(), "stage": stage, **fields}
        with open(self.path("run_log"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")

    def warn(self, stage: str, message: str) -> None:
        self.warnings.append(message)
        self.log(stage, level="warning", message=message)

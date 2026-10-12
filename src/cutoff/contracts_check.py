"""Run-folder contract validator (Phase 0, frozen).

`validate_run_dir(run_dir, keys)` checks that contract files exist, rasters sit
exactly on the run grid with the agreed dtype/band count/value domain, vectors carry
the grid CRS and required columns, and results.json validates. The pipeline calls it
after every stage; each owner's tests call it on their stage output.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np

from cutoff.contracts import (OPTIONAL_RASTERS, OPTIONAL_VECTORS, OTHER_FILES, RASTERS, VECTORS,
                              Disturbance, HazardClass)
from cutoff.geo.grid import Grid


class ContractError(ValueError):
    pass


def _check_raster(run_dir: Path, key: str, grid: Grid) -> list[str]:
    import rasterio

    name, bands, dtype, _nodata, _owner = RASTERS[key]
    errs = []
    with rasterio.open(run_dir / name) as ds:
        if ds.crs is None or ds.crs.to_epsg() != grid.epsg:
            errs.append(f"{name}: CRS {ds.crs} != EPSG:{grid.epsg}")
        if (ds.width, ds.height) != (grid.width, grid.height):
            errs.append(f"{name}: shape {(ds.width, ds.height)} != grid {(grid.width, grid.height)}")
        if not np.allclose(tuple(ds.transform)[:6], grid.transform, atol=1e-6):
            errs.append(f"{name}: transform {tuple(ds.transform)[:6]} != grid {grid.transform}")
        if ds.count != bands:
            errs.append(f"{name}: {ds.count} bands, expected {bands}")
        if ds.dtypes[0] != dtype:
            errs.append(f"{name}: dtype {ds.dtypes[0]}, expected {dtype}")
        if not errs:
            arr = ds.read()
            if key == "hazard_class":
                bad = set(np.unique(arr).tolist()) - {c.value for c in HazardClass}
                if bad:
                    errs.append(f"{name}: unknown class codes {sorted(bad)}")
            elif key == "disturb":
                bad = set(np.unique(arr).tolist()) - {d.value for d in Disturbance}
                if bad:
                    errs.append(f"{name}: unknown disturbance codes {sorted(bad)}")
            elif key in ("shadow_layover",):
                if not set(np.unique(arr).tolist()) <= {0, 1}:
                    errs.append(f"{name}: values must be 0/1")
            elif key == "p_model":
                s = np.nansum(arr, axis=0)
                valid = np.isfinite(arr).all(axis=0)
                if valid.any() and not np.allclose(s[valid], 1.0, atol=1e-3):
                    errs.append(f"{name}: class probabilities must sum to 1 on valid pixels")
            elif key in ("s1_pre_mean", "s1_post"):
                finite = arr[np.isfinite(arr)]
                if finite.size and (finite.min() < 0 or finite.max() > 50):
                    errs.append(f"{name}: expected LINEAR sigma0 (0..~1), got range "
                                f"{finite.min():.3g}..{finite.max():.3g} (dB written by mistake?)")
    return errs


def _check_vector(run_dir: Path, key: str, grid: Grid) -> list[str]:
    import geopandas as gpd

    name, _geom, cols, _owner = VECTORS[key]
    gdf = gpd.read_file(run_dir / name)
    errs = []
    if gdf.crs is None or gdf.crs.to_epsg() != grid.epsg:
        errs.append(f"{name}: CRS {gdf.crs} != EPSG:{grid.epsg}")
    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        errs.append(f"{name}: missing columns {missing}")
    if "status" in gdf.columns:
        from cutoff.contracts import ACCESS_STATUSES
        bad = set(gdf["status"].dropna()) - set(ACCESS_STATUSES)
        if bad:
            errs.append(f"{name}: unknown statuses {bad}")
    return errs


def validate_run_dir(run_dir: str | Path, keys: Iterable[str] | None = None,
                     require_optional: bool = False) -> None:
    """Raise ContractError listing every violation. keys=None checks every contract file present
    in the folder plus all mandatory ones."""
    run_dir = Path(run_dir)
    grid_path = run_dir / OTHER_FILES["grid"]
    if not grid_path.exists():
        raise ContractError(f"{grid_path} missing - the pipeline writes grid.json before any stage")
    grid = Grid.from_json(grid_path)
    if keys is None:
        keys = [k for k in list(RASTERS) + list(VECTORS) + ["results"]]
    errs: list[str] = []
    for key in keys:
        if key == "results":
            p = run_dir / OTHER_FILES["results"]
            if not p.exists():
                errs.append("results.json missing")
                continue
            from cutoff.report.schema import Results
            try:
                Results.model_validate(json.loads(p.read_text(encoding="utf-8")))
            except Exception as e:  # pydantic.ValidationError
                errs.append(f"results.json invalid: {e}")
            continue
        optional = key in OPTIONAL_RASTERS or key in OPTIONAL_VECTORS
        name = RASTERS[key][0] if key in RASTERS else VECTORS[key][0]
        if not (run_dir / name).exists():
            if optional and not require_optional:
                continue
            errs.append(f"{name} missing")
            continue
        errs += _check_raster(run_dir, key, grid) if key in RASTERS else _check_vector(run_dir, key, grid)
    if errs:
        raise ContractError("contract violations:\n  - " + "\n  - ".join(errs))

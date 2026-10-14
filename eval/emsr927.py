"""Check-only comparison. Real references are read only after a clean frozen-v1 tag."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import rasterize, shapes
from scipy import ndimage
from shapely.geometry import box, shape

from cutoff.contracts import EMS_CREDIT
from cutoff.contracts_check import validate_run_dir
from cutoff.report.schema import Results

ROOT = Path(__file__).resolve().parents[1]
CAUSES = ("cloud/timing", "radar geometry", "DEM/gorge", "definition mismatch", "OSM")


def require_freeze(root=ROOT):
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        tag = git("describe", "--tags", "--exact-match", "HEAD")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Real evaluation requires the exact frozen-v1 tag") from exc
    if tag != "frozen-v1":
        raise RuntimeError("Real evaluation requires the exact frozen-v1 tag")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Real evaluation refuses a dirty checkout")
    return git("rev-parse", "HEAD")


def scores(pred, truth, valid):
    tp = int((pred & truth & valid).sum())
    fp = int((pred & ~truth & valid).sum())
    fn = int((~pred & truth & valid).sum())

    def div(a, b):
        return a / b if b else None

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": div(tp, tp + fp),
        "recall": div(tp, tp + fn),
        "f1": div(2 * tp, 2 * tp + fp + fn),
        "iou": div(tp, tp + fp + fn),
    }


def boundary_f1(pred, truth, valid, pixel_m, tolerance_m=30):
    interior = ndimage.binary_erosion(valid, structure=np.ones((3, 3)), border_value=0)

    def boundary(mask):
        return (
            mask ^ ndimage.binary_erosion(mask, structure=np.ones((3, 3)))
        ) & interior

    pb, tb = boundary(pred), boundary(truth)
    if not pb.any() or not tb.any():
        return None
    precision = float(
        (
            ndimage.distance_transform_edt(~tb, sampling=pixel_m)[pb] <= tolerance_m
        ).mean()
    )
    recall = float(
        (
            ndimage.distance_transform_edt(~pb, sampling=pixel_m)[tb] <= tolerance_m
        ).mean()
    )
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate_arrays(classes, truth, extent, pixel_m, *, transform=None, buildings=None):
    """Pure synthetic-test entry point. No reference IO or freeze bypass occurs here."""
    classes = np.asarray(classes)
    truth = np.asarray(truth, bool)
    extent = np.asarray(extent, bool)
    if classes.shape != truth.shape or classes.shape != extent.shape:
        raise ValueError("array shapes differ")
    if pixel_m <= 0:
        raise ValueError("pixel size must be positive")
    valid = extent & (classes != 254)
    primary = np.isin(classes, [1, 3, 4])
    possible = np.isin(classes, [1, 2, 3, 4])
    reference_pixels = int((truth & extent).sum())
    result = {
        "credit": EMS_CREDIT,
        "valid_pixels": int(valid.sum()),
        "reference_pixels": reference_pixels,
        "reference_no_observation_share": float(
            (truth & extent & (classes == 254)).sum() / reference_pixels
        )
        if reference_pixels
        else None,
        "primary": scores(primary, truth, valid),
        "including_possible": scores(possible, truth, valid),
        "affected_building_footprint_recall": None,
        "tiles": [],
    }
    for key, pred in [("primary", primary), ("including_possible", possible)]:
        result[key]["boundary_f1_30m"] = boundary_f1(pred, truth, valid, pixel_m)
    if buildings is not None and len(buildings) and transform is not None:
        polygons = [
            shape(g)
            for g, _ in shapes(
                primary.astype(np.uint8), mask=primary & extent, transform=transform
            )
        ]
        union = gpd.GeoSeries(polygons, crs=buildings.crs).union_all()
        result["affected_building_footprint_recall"] = float(
            buildings.intersects(union).mean()
        )
    step = max(1, round(5000 / pixel_m))
    for row in range(0, classes.shape[0], step):
        for col in range(0, classes.shape[1], step):
            sl = np.s_[row : row + step, col : col + step]
            if not extent[sl].any():
                continue
            tile = {
                "row": row,
                "col": col,
                "tile_m": 5000,
                "credit": EMS_CREDIT,
                "valid_pixels": int(valid[sl].sum()),
                **scores(primary[sl], truth[sl], valid[sl]),
            }
            if transform is not None:
                x0, y0 = transform * (col, row)
                x1, y1 = transform * (
                    min(col + step, classes.shape[1]),
                    min(row + step, classes.shape[0]),
                )
                tile["geometry"] = box(
                    min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
                ).__geo_interface__
            result["tiles"].append(tile)
    return result


def load_reference(directory, epsg):
    root = Path(directory)
    files = (
        [root]
        if root.is_file()
        else sorted([*root.rglob("*.shp"), *root.rglob("*.gpkg")])
    )
    events, areas, excluded, footprints = [], [], [], []
    notes = []
    for path in files:
        layers = (
            gpd.list_layers(path)["name"].tolist()
            if path.suffix.lower() == ".gpkg"
            else [None]
        )
        for layer in layers:
            name = (layer or path.stem).lower()
            if not any(
                word in name
                for word in (
                    "observedevent",
                    "areaofinterest",
                    "notanalysed",
                    "builtup",
                )
            ):
                continue
            frame = gpd.read_file(path, layer=layer).to_crs(epsg)
            frame = frame.loc[frame.geometry.notna() & ~frame.geometry.is_empty].copy()
            if "observedevent" in name:
                events.append(frame)
            elif "areaofinterest" in name:
                areas.append(frame)
            elif "notanalysed" in name:
                excluded.append(frame)
            elif "builtup" in name:
                if "damage_gra" in frame:
                    frame = frame.loc[
                        frame.damage_gra.isin(
                            ["Damaged", "Destroyed", "Possibly damaged"]
                        )
                    ]
                polygon = frame.loc[frame.geom_type.isin(["Polygon", "MultiPolygon"])]
                if len(polygon):
                    footprints.append(polygon)
                if len(polygon) < len(frame):
                    notes.append(
                        "Affected built-up layer contains points; no footprint recall for points."
                    )
    if not events or not areas:
        raise ValueError(
            "Reference needs explicit observedEvent and areaOfInterest layers"
        )

    def merged(frames):
        return gpd.GeoSeries(
            [g for frame in frames for g in frame.geometry], crs=epsg
        ).union_all()

    area = merged(areas)
    if excluded:
        area = area.difference(merged(excluded))
    event = merged(events).intersection(area)
    truth = gpd.GeoDataFrame(geometry=[event], crs=epsg)
    extent = gpd.GeoDataFrame(geometry=[area], crs=epsg)
    buildings = (
        gpd.GeoDataFrame(
            geometry=[
                g for frame in footprints for g in frame.geometry if g.intersects(area)
            ],
            crs=epsg,
        )
        if footprints
        else None
    )
    notes.append(
        "Observed-event polygons may represent optical mass movement, not SAR water; reference is not ground truth."
    )
    return truth, extent, buildings, notes


def markdown(record):
    lines = [
        "# E4 - frozen check-only comparison",
        "",
        EMS_CREDIT,
        "",
        f"Run: `{record['run_id']}`; code: `{record['frozen_commit']}`.",
        "No thresholds/model were retuned after comparison. Only shared AOI coverage and observable pixels are scored.",
        "",
        "| mask | precision | recall | F1 | IoU | boundary F1 (30 m) |",
        "|---|---|---|---|---|---|",
    ]
    for key in ("primary", "including_possible"):
        values = [
            record[key][k]
            for k in ("precision", "recall", "f1", "iou", "boundary_f1_30m")
        ]
        lines.append(
            "| "
            + key
            + " | "
            + " | ".join("n/a" if v is None else f"{v:.4f}" for v in values)
            + " |"
        )
    lines += [
        "",
        f"Reference in no-observation: {record['reference_no_observation_share']}",
        f"Affected building footprint recall: {record['affected_building_footprint_recall']}",
        "",
        "## Disagreement taxonomy (human review pending)",
        "",
        "| cause | tile count |",
        "|---|---|",
        *[f"| {cause} | pending |" for cause in CAUSES],
        "",
        *record["notes"],
    ]
    return "\n".join(lines) + "\n"


def evaluate_run(run_dir, reference, report=None):
    commit = require_freeze()
    root = Path(run_dir)
    validate_run_dir(root, keys=["hazard_class", "results"])
    results = Results.model_validate_json(
        (root / "results.json").read_text(encoding="utf-8")
    )
    if results.model_version == "mock":
        raise ValueError("Real check-only evaluation refuses a synthetic mock run")
    output = root / "emsr927_eval.json"
    marker = root / ".emsr927-evaluation-started.json"
    if output.exists() or marker.exists():
        raise RuntimeError(
            "Check-only evaluation already attempted for this run; no retuning/repeat"
        )
    truth, extent, buildings, notes = load_reference(
        reference, results.inputs.grid_epsg
    )
    with rasterio.open(root / "hazard_class.tif") as source:
        classes = source.read(1)
        transform = source.transform
        kwargs = {
            "out_shape": classes.shape,
            "transform": transform,
            "fill": 0,
            "dtype": "uint8",
        }
        ref = rasterize(
            [(g, 1) for g in truth.geometry if not g.is_empty], **kwargs
        ).astype(bool)
        coverage = rasterize(
            [(g, 1) for g in extent.geometry if not g.is_empty], **kwargs
        ).astype(bool)
        if not coverage.any():
            raise ValueError("Reference AOI has no overlap with the run grid")
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(
                {"frozen_commit": commit, "started_utc": datetime.now(UTC).isoformat()},
                stream,
            )
        record = evaluate_arrays(
            classes,
            ref,
            coverage,
            abs(transform.a),
            transform=transform,
            buildings=buildings,
        )
    record.update(
        run_id=results.run_id,
        frozen_commit=commit,
        notes=notes,
        post_datetime=results.inputs.s1_post.datetime.isoformat(),
        hazard_sha256=hashlib.sha256(
            (root / "hazard_class.tif").read_bytes()
        ).hexdigest(),
        reference_files_sha256={
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path(reference).rglob("*")
            if p.suffix.lower() in (".shp", ".dbf", ".gpkg")
        },
        disagreement_taxonomy={cause: None for cause in CAUSES},
    )
    output.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")
    report = Path(report) if report else ROOT / "docs/results/E4.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(markdown(record), encoding="utf-8")
    features = [
        {
            "type": "Feature",
            "geometry": tile["geometry"],
            "properties": {k: v for k, v in tile.items() if k != "geometry"},
        }
        for tile in record["tiles"]
    ]
    (root / "agreement_tiles.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "crs": {
                    "type": "name",
                    "properties": {"name": f"EPSG:{results.inputs.grid_epsg}"},
                },
                "attribution": EMS_CREDIT,
                "features": features,
            }
        ),
        encoding="utf-8",
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        print(evaluate_run(args.run, args.reference, args.report))
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, str(exc) + "\n")


if __name__ == "__main__":
    main()

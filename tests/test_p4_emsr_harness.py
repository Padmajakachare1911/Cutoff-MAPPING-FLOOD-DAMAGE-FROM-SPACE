import importlib.util
import subprocess
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from affine import Affine
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def harness():
    spec = importlib.util.spec_from_file_location(
        "check_only", ROOT / "eval" / "emsr927.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extent_validity_and_no_observation(harness):
    classes = np.array(
        [[1, 1, 1, 1], [1, 254, 0, 1], [0, 0, 0, 1], [1, 1, 1, 1]], dtype=np.uint8
    )
    truth = np.zeros((4, 4), bool)
    truth[1, 1] = True
    truth[1, 2] = True
    extent = np.zeros((4, 4), bool)
    extent[1:3, 1:3] = True
    data = harness.evaluate_arrays(classes, truth, extent, 10)
    scores = data["primary"]
    assert scores["tp"] == 0 and scores["fp"] == 0 and scores["fn"] == 1
    assert data["valid_pixels"] == 3 and data["reference_no_observation_share"] == 0.5
    assert scores["precision"] is None


def test_possible_class_only_in_secondary(harness):
    classes = np.full((20, 20), 0, np.uint8)
    classes[5:15, 5:15] = 2
    truth = classes == 2
    result = harness.evaluate_arrays(classes, truth, np.ones_like(truth), 10)
    assert result["primary"]["recall"] == 0 and result["including_possible"]["iou"] == 1


def test_boundary_tolerance(harness):
    reference = np.zeros((40, 40), bool)
    reference[10:25, 10:25] = True
    shifted = np.zeros_like(reference)
    shifted[10:25, 12:27] = True
    classes = shifted.astype(np.uint8)
    result = harness.evaluate_arrays(classes, reference, np.ones_like(reference), 10)
    assert result["primary"]["boundary_f1_30m"] == 1
    assert result["primary"]["iou"] < 1


def test_object_recall_and_tile_grid(harness):
    transform = Affine(10, 0, 0, 0, -10, 100)
    buildings = gpd.GeoDataFrame(
        geometry=[box(20, 60, 30, 70), box(70, 10, 80, 20)], crs=32645
    )
    classes = np.zeros((10, 10), np.uint8)
    classes[3, 2] = 1
    result = harness.evaluate_arrays(
        classes,
        classes == 1,
        np.ones_like(classes, bool),
        10,
        transform=transform,
        buildings=buildings,
    )
    assert result["affected_building_footprint_recall"] == 0.5
    assert len(result["tiles"]) == 1 and result["tiles"][0]["tile_m"] == 5000
    assert "Copernicus Emergency Management Service" in result["credit"]


def test_freeze_guard_requires_clean_exact_tag(harness, tmp_path):
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "a").write_text("first")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "a"], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-m",
            "first",
        ],
        check=True,
        capture_output=True,
    )
    with pytest.raises(RuntimeError, match="frozen-v1"):
        harness.require_freeze(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "tag", "frozen-v1"],
        check=True,
        capture_output=True,
    )
    assert harness.require_freeze(tmp_path)
    (tmp_path / "a").write_text("dirty")
    with pytest.raises(RuntimeError, match="dirty"):
        harness.require_freeze(tmp_path)


def test_directory_loader_masks_not_analysed(harness, tmp_path):
    extent = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=32645)
    affected = gpd.GeoDataFrame(geometry=[box(0, 0, 50, 100)], crs=32645)
    excluded = gpd.GeoDataFrame(geometry=[box(0, 0, 20, 100)], crs=32645)
    for name, frame in [
        ("areaOfInterestA", extent),
        ("observedEventA", affected),
        ("notAnalysedA", excluded),
    ]:
        frame.to_file(tmp_path / f"EXAMPLE_{name}_v1.gpkg")
    truth, area, buildings, notes = harness.load_reference(tmp_path, 32645)
    assert round(area.geometry.union_all().area) == 8000
    assert buildings is None

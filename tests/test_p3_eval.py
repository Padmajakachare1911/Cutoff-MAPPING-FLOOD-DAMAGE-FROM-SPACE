import importlib.util
from pathlib import Path

import yaml

from cutoff.mock import make_mock_run


def _module():
    path = Path(__file__).parents[1] / "eval" / "access_eval.py"
    spec = importlib.util.spec_from_file_location("access_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_jaccard_handles_empty_and_overlap():
    module = _module()
    assert module.jaccard(set(), set()) == 1
    assert module.jaccard({"a", "b"}, {"b", "c"}) == 1 / 3


def test_scenario_table_and_dropout_are_reproducible(tmp_path):
    module = _module()
    run_dir = make_mock_run(tmp_path / "mock")
    cfg = yaml.safe_load((Path(__file__).parents[1] / "configs" / "default.yaml").read_text())

    table = module.scenario_table(run_dir)
    first = module.dropout_sensitivity(run_dir, cfg, fractions=(0.1,), runs=2, seed=7)
    second = module.dropout_sensitivity(run_dir, cfg, fractions=(0.1,), runs=2, seed=7)

    assert [row["scenario"] for row in table] == ["A", "B", "C"]
    assert table[0]["cut_off_jaccard_vs_A"] == 1
    assert first == second
    assert set(first) == {"A", "B", "C"}

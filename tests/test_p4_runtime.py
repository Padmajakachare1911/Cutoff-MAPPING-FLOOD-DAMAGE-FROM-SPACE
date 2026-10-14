import importlib.util
import json
from pathlib import Path


def test_runtime_preserves_partial_status_and_peak(tmp_path):
    path = Path(__file__).resolve().parents[1] / "eval/runtime.py"
    spec = importlib.util.spec_from_file_location("runtime", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "run.log").write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"t": 10, "stage": "pipeline", "event": "start"},
                {
                    "t": 12,
                    "stage": "model",
                    "event": "complete",
                    "elapsed_s": 2,
                    "peak_rss_mb": 100,
                },
                {"t": 13, "stage": "pipeline", "event": "complete", "partial": True},
            ]
        )
    )
    record = module.collect(tmp_path)
    assert record["pipeline_wall_s"] == 3 and record["peak_rss_mb"] == 100
    assert record["partial"] is True and record["stage_s"]["model"] == 2

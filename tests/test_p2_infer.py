"""P2.5 - b0 baseline, tiled inference, checkpoint contract, stage_model on the mock run."""
import shutil
from datetime import datetime, timezone

import numpy as np
import pytest
import rasterio
import yaml

from cutoff.contracts import CHANNELS, CONTRACT_VERSION, RASTERS
from cutoff.contracts_check import validate_run_dir
from cutoff.geo.grid import Grid
from cutoff.runctx import RunContext

torch = pytest.importorskip("torch")
pytest.importorskip("segmentation_models_pytorch")

from cutoff.ml.baselines import b0_proba, otsu  # noqa: E402
from cutoff.ml.infer import predict_proba, stage_model  # noqa: E402
from cutoff.ml.model import build_model, load_checkpoint, save_checkpoint  # noqa: E402


@pytest.fixture(scope="module")
def mock_src(tmp_path_factory):
    from cutoff.mock import make_mock_run
    return make_mock_run(tmp_path_factory.mktemp("m") / "demo_mock")


def make_ctx(run_dir, model_path="b0"):
    from pathlib import Path
    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "configs" / "default.yaml").read_text())
    return RunContext(run_dir=run_dir, run_id="t", aoi_bbox=(85.32, 28.14, 85.36, 28.18),
                      event_datetime=datetime(2026, 8, 26, 2, 52, tzinfo=timezone.utc),
                      osm_snapshot="2026-07-27T00:00:00Z", mode="cached", cfg=cfg,
                      grid=Grid.from_json(run_dir / "grid.json"), model_path=model_path)


def _meta(**over):
    m = {"channels": list(CHANNELS), "contract_version": CONTRACT_VERSION, "mean": [0.0] * 7, "std": [1.0] * 7,
         "slope_clip": [0.0, 15.0], "temperature": 1.0, "flood_threshold": 0.5, "encoder": "resnet34",
         "use_slope": True, "config_hash": "x", "train_events": ["1"], "val_events": ["2"], "git_commit": "x"}
    m.update(over)
    return m


def test_otsu_splits_bimodal():
    v = np.concatenate([np.random.default_rng(0).normal(-22, 1, 5000), np.random.default_rng(1).normal(-8, 1, 5000)])
    assert -18 < otsu(v) < -12


def test_b0_flags_new_dark_water_not_permanent_water():
    x = np.zeros((7, 30, 30), np.float32)
    x[0] = x[2] = -8.0; x[1] = x[3] = -14.0                    # land, unchanged
    x[2, :10] = -22.0; x[3, :10] = -28.0                        # rows 0-9: new water (post dark, pre bright)
    x[0, 20:] = x[2, 20:] = -23.0                               # rows 20+: permanent water (dark before and after)
    x[4] = x[2] - x[0]; x[5] = x[3] - x[1]
    x[0, 0, 0] = np.nan
    p = b0_proba(x)
    assert p.shape == (3, 30, 30) and np.isnan(p[:, 0, 0]).all()
    assert np.allclose(np.nansum(p, 0)[1:, 1:], 1.0, atol=1e-5)
    assert p[2, 5, 5] > 0.8 and p[2, 25, 5] < 0.2 and p[1, 25, 5] > 0.5 and p[0, 15, 5] > 0.8


def test_tiled_inference_shape_sum_and_nan():
    m = build_model(pretrained=False)
    x = np.random.default_rng(1).normal(size=(7, 300, 260)).astype(np.float32)
    x[:, :5, :5] = np.nan
    p = predict_proba(m, x, tile=224, overlap=64, batch=2)
    assert p.shape == (3, 300, 260) and np.isnan(p[:, 0, 0]).all()
    assert np.allclose(np.nansum(p, 0)[10:, 10:], 1.0, atol=1e-4)


def test_checkpoint_contract(tmp_path):
    m = build_model(pretrained=False)
    save_checkpoint(tmp_path / "ok.pt", m, _meta())
    _, meta = load_checkpoint(tmp_path / "ok.pt")
    assert meta["channels"] == list(CHANNELS)
    with pytest.raises(ValueError):
        save_checkpoint(tmp_path / "bad.pt", m, {"channels": list(CHANNELS)})          # missing meta keys
    save_checkpoint(tmp_path / "wrongch.pt", m, _meta(channels=["a"] * 7))
    with pytest.raises(ValueError, match="channels"):
        load_checkpoint(tmp_path / "wrongch.pt")
    torch.save({"foo": 1}, tmp_path / "junk.pt")
    with pytest.raises(ValueError):
        load_checkpoint(tmp_path / "junk.pt")


def test_stage_model_b0_on_mock_run(mock_src, tmp_path):
    run = tmp_path / "run"; shutil.copytree(mock_src, run); (run / RASTERS["p_model"][0]).unlink()
    out = stage_model(make_ctx(run, "b0"))
    assert out["model_version"] == "b0" and out["flood_threshold"] == 0.5 and out["temperature"] == 1.0
    validate_run_dir(run, keys=["p_model"])
    with rasterio.open(run / "p_model.tif") as ds:
        p = ds.read()
    with rasterio.open(run / "hazard_class.tif") as ds:   # mock truth: class 1/2 = flood corridor
        cls = ds.read(1)
    assert np.nanmean(p[2][np.isin(cls, [1, 2])]) > np.nanmean(p[2][cls == 0]) + 0.3


def test_stage_model_without_override_uses_configured_v1(mock_src, tmp_path, monkeypatch):
    run = tmp_path / 'run'
    shutil.copytree(mock_src, run)
    ctx = make_ctx(run, None)
    expected = str(tmp_path / 'cutoff_unet_v1.pt')
    ctx.cfg['model']['checkpoint'] = expected
    selected = []
    def missing_checkpoint(path, **kwargs):
        selected.append(str(path))
        raise FileNotFoundError('model-v1 checkpoint unavailable')
    monkeypatch.setattr('cutoff.ml.model.load_checkpoint', missing_checkpoint)
    with pytest.raises(FileNotFoundError, match='model-v1'):
        stage_model(ctx)
    assert selected == [expected]


def test_cache_aoi_model_default_uses_configured_v1(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    cfg = yaml.safe_load((root / 'configs/default.yaml').read_text())
    expected = str(tmp_path / 'cutoff_unet_v1.pt')
    cfg['model']['checkpoint'] = expected
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    selected = []
    def model_stage(ctx):
        selected.append(ctx.model_path)
        return {'model_version': 'cutoff_unet_v1.pt'}
    monkeypatch.setattr('cutoff.ml.infer.stage_model', model_stage)
    monkeypatch.setattr('cutoff.contracts_check.validate_run_dir', lambda *args, **kwargs: None)
    spec = importlib.util.spec_from_file_location('cache_aoi_default_audit', root / 'scripts/cache_aoi.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.main(['--name', 'audit', '--bbox', '85.32,28.14,85.36,28.18', '--event',
                        '2026-08-26T02:52:00Z', '--stages', 'model', '--config', str(config),
                        '--out', str(tmp_path / 'run')]) == 0
    assert selected == [expected]


def test_stage_model_checkpoint_on_mock_run(mock_src, tmp_path):
    run = tmp_path / "run"; shutil.copytree(mock_src, run)
    ck = tmp_path / "m.pt"
    save_checkpoint(ck, build_model(pretrained=False), _meta(temperature=2.0, flood_threshold=0.4, use_slope=False))
    out = stage_model(make_ctx(run, str(ck)))
    assert out["temperature"] == 2.0 and out["flood_threshold"] == 0.4 and out["model_version"] == "m.pt"
    validate_run_dir(run, keys=["p_model"])

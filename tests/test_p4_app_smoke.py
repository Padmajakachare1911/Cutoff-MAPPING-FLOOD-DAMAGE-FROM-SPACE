from pathlib import Path

from streamlit.testing.v1 import AppTest

from cutoff.mock import make_mock_run

APP = Path(__file__).resolve().parents[1] / 'app' / 'streamlit_app.py'


def test_mock_app_scenarios_and_downloads(tmp_path, monkeypatch):
    make_mock_run(tmp_path / 'demo_mock')
    monkeypatch.setenv('CUTOFF_OUTPUT_DIR', str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert next(item.value for item in app.selectbox if item.label == 'Model') == 'Checkpoint'
    assert next(item.value for item in app.text_input if item.label == 'Checkpoint path').endswith('cutoff_unet_v1.pt')
    assert any('Educational prototype' in item.value for item in app.warning)
    initial = next(m.value for m in app.metric if m.label == 'Cut off')
    app.sidebar.radio[0].set_value('B').run()
    assert not app.exception
    after = next(m.value for m in app.metric if m.label == 'Cut off')
    assert initial == '2' and after == '1'
    assert any('MOCK DATA' in warning.value for warning in app.warning)


def test_error_run_shows_pair_message(tmp_path, monkeypatch):
    import json
    root = tmp_path / 'bad'
    root.mkdir()
    (root / 'error.json').write_text(json.dumps({'error_type': 'NoValidPair', 'message': 'Tracks seen: 85; next pass'}))
    monkeypatch.setenv('CUTOFF_OUTPUT_DIR', str(tmp_path))
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert any('Tracks seen: 85; next pass' in error.value for error in app.error)


def test_raster_overlay_uses_mercator_and_masks_nodata(tmp_path):
    import importlib.util

    import numpy as np
    root = make_mock_run(tmp_path / 'mock')
    spec = importlib.util.spec_from_file_location('map_layers', APP.with_name('map_layers.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    image, bounds = module.raster_overlay(root / 'hazard_class.tif', 'hazard')
    assert image.shape[-1] == 4 and image.dtype == np.uint8
    assert bounds[0][0] < bounds[1][0] and bounds[0][1] < bounds[1][1]
    assert np.any(image[..., 3] == 0)

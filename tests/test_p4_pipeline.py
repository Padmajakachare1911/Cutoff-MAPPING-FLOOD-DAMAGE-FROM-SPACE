import json
import shutil

import pytest

from cutoff import pipeline
from cutoff.contracts import RASTERS, VECTORS
from cutoff.contracts_check import validate_run_dir
from cutoff.data.s1_pairs import NoValidPair
from cutoff.mock import MOCK_BBOX, make_mock_run


@pytest.fixture
def fake_stages(tmp_path, monkeypatch):
    source = make_mock_run(tmp_path / 'source')
    data = json.loads((source / 'results.json').read_text())
    returns = {
        's1': {k: data['inputs'][k] for k in ('s1_backend', 'rel_orbit', 'orbit_direction', 's1_post',
                                            's1_pre', 'post_lag_hours')},
        's2': {'s2_scenes': [], 's2_clear_fraction': None},
        'model': {'model_version': 'mock', 'flood_threshold': 0.5, 'temperature': 1.0},
        'disturbance': {'sigma_stable_db': 1.1, 'k_sigma': 3.0},
        'gating': {'stable_steep_fpr': 0.0},
        'vectorize': {k: data['hazard'][k] for k in ('area_km2_by_class', 'no_observation_km2')},
        'exposure': data['exposure'], 'access': {'access': data['access']},
    }
    registry = {}
    for name, _, keys in pipeline.STAGES:
        def stage(ctx, name=name, keys=keys):
            for key in keys:
                shutil.copy2(source / (RASTERS | VECTORS)[key][0], ctx.path(key))
            if name == 's1':
                shutil.copy2(source / 'pairs.json', ctx.path('pairs'))
            return returns.get(name, {})
        registry[name] = stage
    monkeypatch.setattr(pipeline, 'resolve_stage', lambda name, target: registry[name], raising=False)
    monkeypatch.setattr(pipeline, 'render_report', lambda results, root: None, raising=False)
    return registry, tmp_path


def execute(fake_stages, **kwargs):
    _, tmp = fake_stages
    return pipeline.run(MOCK_BBOX, '2026-08-26T02:52:00Z', out_root=tmp / 'runs', **kwargs)


def test_complete_run_and_timings(fake_stages):
    root = execute(fake_stages, run_id='complete')
    validate_run_dir(root)
    data = json.loads((root / 'results.json').read_text())
    assert data['exposure'] is not None and len(data['access']) == 3
    assert set(data['timings_s']) >= {name for name, _, _ in pipeline.STAGES}
    logs = [json.loads(line) for line in (root / 'run.log').read_text().splitlines()]
    assert any(rec.get('peak_rss_mb', 0) > 0 for rec in logs)
    assert len(data['limitations']) >= 8


def test_osm_failure_is_partial_and_skips_dependents(fake_stages):
    registry, _ = fake_stages
    def fail(ctx):
        raise RuntimeError('OSM unavailable')
    registry['osm'] = fail
    registry['access'] = lambda ctx: pytest.fail('dependent stage ran')
    root = execute(fake_stages)
    data = json.loads((root / 'results.json').read_text())
    assert data['exposure'] is None and data['access'] == []
    assert any('partial' in w.lower() and 'OSM unavailable' in w for w in data['warnings'])


def test_optional_failure_removes_partial_s2(fake_stages):
    registry, _ = fake_stages
    def fail(ctx):
        ctx.path('s2_water').write_bytes(b'broken')
        raise OSError('S2 absent')
    registry['s2'] = fail
    root = execute(fake_stages)
    assert (root / 'results.json').exists() and not (root / 's2_water.tif').exists()


def test_hard_failure_has_only_error(fake_stages):
    registry, tmp = fake_stages
    def fail(ctx):
        raise NoValidPair('Tracks seen: 85 ascending; next pass tomorrow')
    registry['s1'] = fail
    with pytest.raises(NoValidPair, match='Tracks seen'):
        execute(fake_stages, run_id='bad')
    root = tmp / 'runs' / 'bad'
    assert not (root / 'results.json').exists()
    assert json.loads((root / 'error.json').read_text())['message'].startswith('Tracks seen')


def test_date_warning_and_utc(fake_stages):
    _, tmp = fake_stages
    root = pipeline.run(MOCK_BBOX, '2026-08-26', out_root=tmp / 'runs')
    data = json.loads((root / 'results.json').read_text())
    assert data['inputs']['event_datetime'] == '2026-08-26T23:59:59Z'
    assert any('same-day' in w for w in data['warnings'])


def test_invalid_request_cannot_create_outputs(fake_stages):
    _, tmp = fake_stages
    with pytest.raises(ValueError, match='before'):
        execute(fake_stages, osm_snapshot='2026-09-01T00:00:00Z')
    with pytest.raises(ValueError, match='run_id'):
        execute(fake_stages, run_id='../escape')
    assert not (tmp / 'runs').exists()


def test_existing_run_never_overwritten(fake_stages):
    execute(fake_stages, run_id='one')
    with pytest.raises(FileExistsError):
        execute(fake_stages, run_id='one')


def test_unsafe_stage_subset_rejected(fake_stages):
    with pytest.raises(ValueError, match='dependencies'):
        execute(fake_stages, stages=['gating'])


def test_osm_cache_namespace_changes_with_snapshot(fake_stages):
    registry, _ = fake_stages
    roots = []
    original = registry['osm']
    def remember(ctx):
        roots.append(ctx.cfg['run']['cache_dir'])
        return original(ctx)
    registry['osm'] = remember
    execute(fake_stages, osm_snapshot='2026-07-01T00:00:00Z')
    execute(fake_stages, osm_snapshot='2026-07-02T00:00:00Z')
    assert roots[0] != roots[1]


def test_cli_pair_exit_is_clean(monkeypatch, capsys):
    from cutoff.cli import main
    def fail(**kwargs):
        raise NoValidPair('Tracks seen: next expected pass')
    monkeypatch.setattr(pipeline, 'run', fail)
    assert main(['run', '--bbox', '85.32,28.14,85.36,28.18', '--event', '2026-08-26']) == 2
    assert capsys.readouterr().err.strip() == 'Tracks seen: next expected pass'

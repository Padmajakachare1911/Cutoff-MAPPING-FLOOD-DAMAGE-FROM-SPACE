import json
import shutil

from cutoff import pipeline
from cutoff.contracts import RASTERS, VECTORS
from cutoff.contracts_check import validate_run_dir
from cutoff.mock import MOCK_BBOX, make_mock_run


def test_actual_hazard_exposure_access_and_pdf(tmp_path, monkeypatch):
    """Only acquisition is synthetic; actual P2/P3 algorithms and P4 product are integrated."""
    source=make_mock_run(tmp_path/'inputs')
    original=pipeline.resolve_stage
    record=json.loads((source/'results.json').read_text(encoding='utf-8'))
    def resolve(name,target):
        if name not in {'s1','terrain','s2','osm'}:
            return original(name,target)
        keys=next(keys for stage,_,keys in pipeline.STAGES if stage==name)
        def stage(ctx):
            for key in keys:
                shutil.copy2(source/(RASTERS|VECTORS)[key][0],ctx.path(key))
            if name=='s1':
                shutil.copy2(source/'pairs.json',ctx.path('pairs'))
                return {key:record['inputs'][key] for key in
                    ('s1_backend','rel_orbit','orbit_direction','s1_pre','s1_post','post_lag_hours')}
            if name=='s2':
                return {'s2_scenes':record['inputs']['s2_scenes'],
                        's2_clear_fraction':record['inputs']['s2_clear_fraction']}
            return {}
        return stage
    monkeypatch.setattr(pipeline,'resolve_stage',resolve)
    root=pipeline.run(MOCK_BBOX,'2026-08-26T02:52:00Z',model='b0',out_root=tmp_path/'runs',run_id='integration')
    validate_run_dir(root)
    results=json.loads((root/'results.json').read_text(encoding='utf-8'))
    assert results['model_version']=='b0'
    assert results['exposure'] is not None and len(results['access'])==3
    assert (root/'sitrep.pdf').is_file()
    assert not any('Partial run' in warning for warning in results['warnings'])

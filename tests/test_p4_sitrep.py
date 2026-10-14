import json

import pytest
from jinja2 import UndefinedError
from pypdf import PdfReader

from cutoff.contracts import ATTRIBUTION
from cutoff.mock import make_mock_run


def test_sitrep_one_page_and_attribution(tmp_path):
    from cutoff.report.sitrep import render
    root = make_mock_run(tmp_path / 'mock')
    html, pdf = render(root / 'results.json', root)
    reader = PdfReader(pdf)
    assert len(reader.pages) == 1 and html.is_file()
    text = reader.pages[0].extract_text()
    assert 'Educational prototype' in text
    for credit in ATTRIBUTION[:3]:
        assert credit in text.replace('\n', ' ')
    assert 'Upper Village' in text and 'Scenario' in text


def test_missing_template_field_raises(tmp_path):
    from cutoff.report.sitrep import render_html
    root = make_mock_run(tmp_path / 'mock')
    data = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    del data['hazard']['no_observation_km2']
    with pytest.raises(UndefinedError):
        render_html(data)


def test_partial_and_long_list_stay_one_page(tmp_path):
    from cutoff.report.sitrep import render
    root = make_mock_run(tmp_path / 'mock')
    data = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    data['exposure'] = None
    scenario = data['access'][1]
    scenario['cut_off'] = [dict(scenario['cut_off'][0], sid=f'S{i}', name='Very long settlement name ' * 4)
                           for i in range(40)]
    scenario['counts']['cut_off'] = 40
    data['warnings'] = ['Partial run: OSM failure ' + 'detail ' * 100] * 12
    html, pdf = render(data, root)
    assert len(PdfReader(pdf).pages) == 1
    text = PdfReader(pdf).pages[0].extract_text()
    assert '+25 more' in text and 'Unavailable' in text


def test_html_escapes_untrusted_names(tmp_path):
    from cutoff.report.sitrep import render_html
    root = make_mock_run(tmp_path / 'mock')
    data = json.loads((root / 'results.json').read_text(encoding='utf-8'))
    data['access'][1]['cut_off'][0]['name'] = '<script>alert(1)</script>'
    html = render_html(data)
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_fallback_renderer(tmp_path, monkeypatch):
    from cutoff.report import sitrep
    root = make_mock_run(tmp_path / 'mock')
    def unavailable(*args):
        raise OSError('pango unavailable')
    monkeypatch.setattr(sitrep, '_weasyprint', unavailable)
    _, pdf = sitrep.render(root / 'results.json', root)
    assert len(PdfReader(pdf).pages) == 1

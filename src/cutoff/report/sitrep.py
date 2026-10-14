"""One-page situation report, rendered entirely from the Results record."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from cutoff.report.schema import Results

TEMPLATES = Path(__file__).with_name('templates')
ENV = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined, autoescape=True)
ENV.filters['shortest'] = lambda items: sorted(items, key=len)[:5]


def _data(results):
    if isinstance(results, (str, Path)):
        results = json.loads(Path(results).read_text(encoding='utf-8'))
    if isinstance(results, Results):
        return results.model_dump(mode='json')
    return results


def render_html(results, font_size=9):
    """Accept raw dictionaries too, so StrictUndefined exposes missing fields."""
    return ENV.get_template('sitrep.html.j2').render(r=_data(results), font_size=font_size)


def _weasyprint(html, path):
    from weasyprint import HTML
    HTML(string=html, base_url=str(TEMPLATES)).write_pdf(path)


def _fallback(html, path):
    from xhtml2pdf import pisa
    with path.open('wb') as output:
        result = pisa.CreatePDF(html, dest=output, encoding='utf-8')
    if result.err:
        raise RuntimeError('PDF fallback could not render the situation report')


def render(results, run_dir):
    """Return (HTML, PDF); use WeasyPrint, then xhtml2pdf on unavailable native libraries.

    Bound presentation lengths and try compact typography if a renderer paginates.
    Refuse a multi-page result instead of silently breaking the sitrep requirement.
    """
    from pypdf import PdfReader
    data = _data(results)
    Results.model_validate(data)
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    html_path, pdf_path = root / 'sitrep.html', root / 'sitrep.pdf'
    renderer = _weasyprint
    for size in (9, 8, 7):
        html = render_html(data, font_size=size)
        html_path.write_text(html, encoding='utf-8')
        try:
            renderer(html, pdf_path)
        except (ImportError, OSError):
            renderer = _fallback
            renderer(html, pdf_path)
        if len(PdfReader(pdf_path).pages) == 1:
            return html_path, pdf_path
    pdf_path.unlink(missing_ok=True)
    raise RuntimeError('Situation report exceeds one page; full data remains in results.json')

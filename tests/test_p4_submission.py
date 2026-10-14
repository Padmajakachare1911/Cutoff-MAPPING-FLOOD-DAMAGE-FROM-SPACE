import base64
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]


def test_report_page_budget_and_honest_status():
    reader = PdfReader(ROOT / "docs/report/report.pdf")
    assert len(reader.pages) <= 6
    text = " ".join(page.extract_text() for page in reader.pages)
    assert "educational prototype" in text.lower()
    assert "No real EMSR927 comparison has occurred" in text
    assert "partial" in text and "OSM" in text
    assert "OpenStreetMap contributors" in text
def test_report_image_links_work_after_checkout_moves():
    root = Path(__file__).resolve().parents[1] / 'docs/report'
    text = (root / 'report.html').read_text(encoding='utf-8')
    images = re.findall(r'<img[^>]+src="([^"]+)"', text)
    assert images
    for src in images:
        if src.startswith('data:image/png;base64,'):
            assert base64.b64decode(src.split(',', 1)[1], validate=True).startswith(b'\x89PNG\r\n\x1a\n')
            continue
        assert not Path(src).is_absolute() and not re.match(r'^[A-Za-z]:', src)
        assert (root / src).is_file()
    for src in re.findall(r'<img[^>]+src="([^"]+)"', (root / 'report.md').read_text(encoding='utf-8')):
        assert not Path(src).is_absolute() and not re.match(r'^[A-Za-z]:', src)
        assert (root / src).is_file()

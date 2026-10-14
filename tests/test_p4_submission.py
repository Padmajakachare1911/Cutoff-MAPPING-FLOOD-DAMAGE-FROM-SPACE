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

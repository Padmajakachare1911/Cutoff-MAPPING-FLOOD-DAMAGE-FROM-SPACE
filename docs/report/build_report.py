"""Rebuild the six-page report from committed evidence snapshots and measured results."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader

from cutoff.contracts import ATTRIBUTION, DISCLAIMER
from cutoff.report.sitrep import _fallback, _weasyprint

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent


def font(size):
    for name in (
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(name).exists():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default(size=size)


def diagram():
    image = Image.new("RGB", (1200, 260), "#f5f8fa")
    draw = ImageDraw.Draw(image)
    labels = [
        ("P1 / OBSERVE", "Same-track SAR\nTerrain + optional S2"),
        ("P2 / EVIDENCE", "Model + change\nTerrain-gated hazard"),
        ("P3 / CONSEQUENCES", "Pre-event exposure\nA / B / C road access"),
        ("P4 / PRODUCT", "Validated Results\nDashboard + PDF"),
    ]
    for i, (title, subtitle) in enumerate(labels):
        x = 25 + i * 295
        draw.rounded_rectangle((x, 45, x + 260, 220), radius=18, fill="#123b4a")
        draw.text((x + 16, 65), title, font=font(19), fill="#7bd7d0")
        draw.multiline_text(
            (x + 16, 110), subtitle, font=font(19), fill="white", spacing=12
        )
        if i < 3:
            draw.text((x + 267, 118), ">", font=font(32), fill="#123b4a")
    image.save(OUT / "pipeline.png")


def hazard_figure():
    path = ROOT / "outputs/c2-trishuli-north-model/hazard_class.tif"
    if not path.exists():
        return
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import rasterio
    from matplotlib.patches import Patch

    palette = {
        0: "#edf1f5",
        1: "#0879bd",
        2: "#80c8e7",
        3: "#cf930c",
        4: "#b23b27",
        5: "#394e99",
        254: "#727d85",
    }
    with rasterio.open(path) as src:
        data = src.read(1, out_shape=(min(1000, src.height), min(1000, src.width)))
        width, height = src.width * 10 / 1000, src.height * 10 / 1000
    rgba = np.ones((*data.shape, 4))
    for code, color in palette.items():
        rgba[data == code] = matplotlib.colors.to_rgba(color)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.imshow(rgba, extent=(0, width, 0, height), origin="upper")
    ax.set(
        xlabel="Projected grid km",
        ylabel="Projected grid km",
        title="Trishuli north / released model / partial integration",
    )
    names = {
        1: "Flood high",
        2: "Flood possible",
        3: "Rule decrease",
        4: "Rule increase",
        5: "Permanent water",
        254: "No observation",
    }
    ax.legend(
        handles=[Patch(color=palette[k], label=v) for k, v in names.items()],
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
    )
    fig.tight_layout()
    fig.savefig(OUT / "hazard_north.png", dpi=150)
    plt.close(fig)


def table(headers, rows):
    return (
        "<table><tr>"
        + "".join(f"<th>{html.escape(str(x))}</th>" for x in headers)
        + "</tr>"
        + "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(x))}</td>" for x in row) + "</tr>"
            for row in rows
        )
        + "</table>"
    )


def main():
    OUT.mkdir(exist_ok=True)
    evidence = OUT / "evidence"
    evidence.mkdir(exist_ok=True)
    for name in (
        "c1-trishuli-north-b0",
        "c2-trishuli-north-model",
        "c2-deir-ez-zor-model",
        "demo_mock",
    ):
        source = ROOT / "outputs" / name / "results.json"
        if source.exists():
            (evidence / f"{name}.json").write_text(
                source.read_text(encoding="utf-8"), encoding="utf-8"
            )
    diagram()
    hazard_figure()
    kuro = json.loads((ROOT / "docs/results/raw/test_b0_b1_early_b3.json").read_text())
    selected = [
        r
        for r in kuro["results"]
        if r["name"] in ("b0", "b1_snunet_pre_post", "b3_no_slope")
    ]
    final = next(r for r in selected if r["name"] == "b3_no_slope")
    e7 = json.loads((ROOT / "docs/results/raw/E7.json").read_text())
    metrics = table(
        ["Model", "Precision", "Recall", "F1", "IoU"],
        [
            [
                r["name"],
                *[
                    f"{r['pooled'][k]:.3f}"
                    for k in ("precision", "recall", "f1", "iou")
                ],
            ]
            for r in selected
        ],
    )
    strata = [
        r
        for r in final["strata"]
        if r["event"] == "ALL" and isinstance(r["slope_bin"], int)
    ]
    slope = table(
        ["Slope bin", "Flood support pixels", "IoU", "F1"],
        [
            [
                ["0-5 deg", "5-15 deg", ">=15 deg"][r["slope_bin"]],
                r["support_px"],
                f"{r['iou']:.3f}",
                f"{r['f1']:.3f}",
            ]
            for r in strata
        ],
    )
    runtime = table(
        ["Real run", "Mode", "Pipeline seconds", "Peak RSS MB", "State"],
        [
            [
                r["run"],
                r["mode"],
                f"{r['pipeline_wall_s']:.2f}",
                f"{r['peak_rss_mb']:.2f}",
                "partial",
            ]
            for r in e7["runs"]
        ],
    )

    def source(text):
        return f'<p class="source">Source: {html.escape(text)}</p>'

    def image_uri(name):
        return "data:image/png;base64," + base64.b64encode(
            (OUT / name).read_bytes()
        ).decode("ascii")

    pages = [
        (
            "Cutoff / Flood exposure and access",
            f'<p class="notice">{DISCLAIMER}</p><h2>Abstract</h2><p>Cutoff is an educational prototype for rescue planning. Given an area and event time, it combines same-track radar change, a flood model, terrain and pre-event infrastructure to answer three questions: where did the event leave evidence, what was exposed, and who may be cut off? The product is a map dashboard and one-page situation report driven by a validated Results record.</p><h2>System overview</h2><img src="{(OUT / "pipeline.png").as_posix()}" width="520"><h2>Current delivery</h2><p>P1-P3 algorithms and the P4 product are implemented. Pipeline/CLI, strict PDF, dashboard, feature CI, isolated-install checks, guarded evaluation and runtime tooling are delivered. Real hazard case studies completed; full access integration is awaiting data remediation. E4/freeze and human rehearsal remain explicit handoff checks.</p><h2>Users and boundaries</h2><p>Settlement-scale prioritisation and evidence review, rather than structural damage assessment. Every display carries the prototype disclaimer. Missing observations and unmapped access are represented as uncertainty.</p>'
            + source("docs/plan/00_MASTER_PLAN.md; docs/plan/reports/P4.1-P4.7.md"),
        ),
        (
            "Methods / consistent observations",
            "<h2>Acquisition and preprocessing</h2><p>Choose a post-event pass strictly after the supplied UTC timestamp and up to three pre-event passes from the same relative orbit/direction. Require VV/VH and adequate footprint coverage. Bare dates mean end of day. Store linear sigma-zero, apply Lee Sigma and average pre-event scenes in linear units. Fast processing uses CDSE Sentinel Hub; full processing uses SNAP. Buffered Copernicus GLO-30 provides slope, HAND and drainage.</p><h2>Model and evidence</h2><p>The seven-channel U-Net uses pre/post VV/VH dB, their differences and slope, with the released no-slope model holding the slope channel at its training mean. Calibration/threshold selection uses validation events only. A scene-wide robust change scale identifies coherent decreases/increases in the drainage corridor. Terrain/S2 evidence adjusts confidence; shadow/layover and invalid data become no observation.</p><h2>Exposure and access</h2><p>Intersect hazard with strictly pre-event OSM. Split roads at valid intersections, retain keyed parallel edges, and compare baseline/post-closure travel time to mapped targets. Scenario A uses proximity to all hazard, B sustained high-confidence overlap, C bridge approaches. Report connected/degraded/cut off/unknown separately and retain trail access. No operational closure is asserted.</p><h2>Product integrity</h2><p>Validate stage outputs on the shared UTM grid before consumers run. Optional optical errors continue; infrastructure errors publish a partial report; core acquisition errors preserve their diagnostic. The dashboard and PDF read Results statistics. OSM caches are isolated by snapshot/settings in P4.</p>"
            + source(
                "docs/plan/05_contracts.md; configs/default.yaml; docs/plan/reports/P1_HANDOFF.md; P2_HANDOFF.md; P3_HANDOFF.md"
            ),
        ),
        (
            "Held-out evaluation / global floods",
            "<h2>E1 - measured flood-class performance</h2>"
            + metrics
            + source(
                "docs/results/raw/test_b0_b1_early_b3.json; docs/results/P2_kuro_results.md"
            )
            + "<h2>E2 - final model by slope stratum</h2>"
            + slope
            + source("same raw file, final model strata, ALL events")
            + "<p>The official event-level split reduces within-event leakage. Training/calibration decisions were made before the Himalayan check. Steep-terrain support is much smaller than lowland support, so global scores do not establish Himalayan reliability. Model scores are calibrated global-flood scores, not verified local probabilities.</p><h2>Other measured experiments</h2><p>P1 documents same-track/cross-track and fast/full comparisons (E5/E3c). The fast/full stable VV median difference was 0.59 dB and the downstream hazard agreement was sensitive to change-scale differences. These are limitations to report, not reasons to tune on the check-only case.</p>"
            + source(
                "docs/results/E3c.md; docs/results/E5.md; docs/results/raw/val_e8.json"
            ),
        ),
        (
            "Case studies / integration and timing",
            f'<img src="{(OUT / "hazard_north.png").as_posix()}" width="450">'
            + source(
                "docs/report/evidence/c2-trishuli-north-model.json and its run hazard_class.tif; modified Copernicus Sentinel data 2026"
            )
            + "<h2>E7 - actual pipeline measurements</h2>"
            + runtime
            + source("docs/results/raw/E7.json; named real run.log files")
            + "<p>Timings use warm satellite caches or cached mode, omit CLI startup, and stop with unavailable OSM/access. RSS includes child processes and excludes GPU VRAM. They do not substitute for a cold 10/20/40 km sweep. [TARGET] 20 x 20 km fast mode within ten minutes remains unverified.</p>",
        ),
        (
            "Limitations / evidence still pending",
            "<h2>E4 and E6</h2><p>No real EMSR927 comparison has occurred. The check-only harness is complete and tested with synthetic polygons. After corrected-data integration, freeze clean code/config/model and run it once. The optical observed-event layer represents mass movement, creating a definition mismatch with SAR water. Point-only reference buildings do not establish footprint recall. Human tile taxonomy remains necessary.</p><p>E6 tooling and algorithm tests exist; real buffered access/scenario/dropout measurements require a verified OSM v2 key or dated caches. The upstream v1 geometry fallback is restricted. The teammate owns the underlying data-integrity remediation.</p><h2>Scientific and operational limits</h2><p>Overpasses can miss the peak; this is not early warning. Ten-metre pixels omit narrow roads/bridges. Shadow/layover are unobservable. Wet mud may resemble water; rough debris is statistical change. Surface DEM and gorge smoothing influence HAND/slope. Permanent-water scores can include steep back-slopes and are excluded from hazard exposure. OSM incompleteness can change access status; unknown means unmapped, not safe.</p><h2>Readiness limits</h2><p>Competition permission for cached/fast processing and pretrained encoders is unconfirmed. Independent teammate fresh-clone and unprepared-AOI rehearsal remain pending. Submission evidence must retain these distinctions; targets and synthetic demonstrations are not real-world accuracy results.</p>"
            + source(
                "docs/results/E4.md; docs/results/E6.md; docs/results/E7.md; docs/plan/reports/organiser_answers.md; issues #25 and #31"
            ),
        ),
        (
            "Attribution / reproducibility / handoff",
            "<h2>Required credit</h2>"
            + "".join(f"<p>{html.escape(a)}</p>" for a in ATTRIBUTION)
            + "<p>European Union, Copernicus Emergency Management Service data (check-only reference inventory/evaluation).</p><h2>Reproduce the product</h2><p>Follow README: clean environment, install dev/app/pdf extras, create the labelled synthetic demo and open Streamlit. The released model checksum is recorded in the P2 handoff. Feature branches and task reports document acceptance checks. Code licence: MIT; source data retain upstream licences.</p><h2>Finish data-dependent evidence</h2><ol><li>Resolve verified pre-event OSM coverage and authenticate live inputs.</li><li>Rerun complete Trishuli north/south and a non-Trishuli AOI; validate contracts and dashboard.</li><li>Review final code/config/checkpoint, create frozen-v1, then run E4 once without retuning.</li><li>Run E6 and the cold-size E7 sweep; have a teammate rehearse a fresh clone and unprepared AOI.</li><li>Refresh this report, video and submission checklist from actual results before submitting.</li></ol><h2>Primary reproducibility sources</h2><p>docs/plan/05_contracts.md; docs/results/P2_kuro_results.md and raw/test_b0_b1_early_b3.json; E3c.md; E5.md; E4.md; E6.md; E7.md and raw/E7.json; docs/plan/reports/P4.0-P4.9.md; docs/report/evidence/*.json; ATTRIBUTION.md.</p>",
        ),
    ]
    css = "@page {size:A4;margin:15mm;} body {font:10pt Helvetica;color:#213444;line-height:1.35} h1{font-size:23pt;color:#123b4a} h2{font-size:13pt;color:#126575;margin-top:16pt} p{margin:7pt 0} .page{page-break-before:always}.first{page-break-before:auto} table{width:100%;font-size:8pt} th{background:#e7eff2;text-align:left} td,th{padding:5pt;border-bottom:0.5pt solid #d9e1e5}.source{font-size:7pt;color:#526572}.notice{background:#fff0d1;padding:8pt} img{margin:8pt 0}"
    document = (
        '<html><head><meta charset="utf-8"><style>'
        + css
        + "</style></head><body>"
        + "".join(
            f'<div class="page {"first" if i == 0 else ""}"><p class="source">CUTOFF / P4 delivery report / {i + 1}</p><h1>{title}</h1>{body}</div>'
            for i, (title, body) in enumerate(pages)
        )
        + "</body></html>"
    )
    for name in ("pipeline.png", "hazard_north.png"):
        document = document.replace((OUT / name).as_posix(), image_uri(name))
    (OUT / "report.html").write_text(document, encoding="utf-8")
    (OUT / "report.md").write_text(
        "\n\n".join("# " + title + "\n\n" + body for title, body in pages),
        encoding="utf-8",
    )
    try:
        _weasyprint(document, OUT / "report.pdf")
    except (ImportError, OSError):
        _fallback(document, OUT / "report.pdf")
        # xhtml2pdf/ReportLab can reuse the first raster when multiple images are
        # embedded. Overlay the second figure at its actual PDF image rectangle.
        import pymupdf
        with pymupdf.open(OUT / 'report.pdf') as pdf:
            page = pdf[3]
            rect = pymupdf.Rect(page.get_image_info()[0]['bbox'])
            page.draw_rect(rect, color=None, fill=(1, 1, 1), overlay=True)
            page.insert_image(rect, filename=str(OUT / 'hazard_north.png'), overlay=True)
            repaired = OUT / 'report.repaired.pdf'
            pdf.save(repaired)
        repaired.replace(OUT / 'report.pdf')
    count = len(PdfReader(OUT / "report.pdf").pages)
    if count > 6:
        raise RuntimeError(f"Report exceeds six pages: {count}")
    print("Report verified:", count, "pages")


if __name__ == "__main__":
    main()

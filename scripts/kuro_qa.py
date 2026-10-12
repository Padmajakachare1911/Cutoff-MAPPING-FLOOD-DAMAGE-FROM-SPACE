"""P2.3 QA: plot random Kuro Siwo samples per split and summarise class / slope distributions.

    python scripts/kuro_qa.py            -> docs/plan/reports/P2.3_qa.png + P2.3_qa.md
"""
from __future__ import annotations

import csv
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cutoff.data.kuro_siwo import load_sample, sample_to_input  # noqa: E402

DATA = Path(os.environ.get("CUTOFF_DATA_DIR", "C:/cutoff_data")) / "kuro"
OUT = ROOT / "docs" / "plan" / "reports"


def main(n_per_split: int = 5, seed: int = 0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = list(csv.DictReader((DATA / "index.csv").open()))
    rng = np.random.default_rng(seed)
    by_split = defaultdict(list)
    for r in rows:
        by_split[r["split"]].append(r)
    splits = [s for s in ("train", "val", "test") if by_split[s]]
    picks = [(s, by_split[s][i]) for s in splits
             for i in rng.choice(len(by_split[s]), size=min(n_per_split, len(by_split[s])), replace=False)]
    fig, axes = plt.subplots(len(picks), 5, figsize=(13, 2.6 * len(picks)))
    axes = np.atleast_2d(axes)
    for row, (s, r) in zip(axes, picks):
        rec = load_sample(DATA / r["path"])
        x = sample_to_input(rec)
        panels = [(x[0], "VV pre dB", "gray", (-25, 0)), (x[2], "VV post dB", "gray", (-25, 0)),
                  (x[4], "dVV dB", "RdBu", (-10, 10)), (x[6], "slope deg (clip 15)", "viridis", (0, 15)),
                  (np.where(rec["valid"] == 1, rec["mask"], np.nan), "label 0/1/2", "tab10", (0, 9))]
        for ax, (a, t, cm, lim) in zip(row, panels):
            ax.imshow(a, cmap=cm, vmin=lim[0], vmax=lim[1]); ax.set_xticks([]); ax.set_yticks([])
            ax.set_title(f"{s}/{r['event']} {t}", fontsize=7)
    fig.tight_layout()
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "P2.3_qa.png", dpi=70)

    lines = ["# P2.3 Kuro Siwo subset QA", "", "| split | events | samples | with flood (>1 %) | mean flood frac | mean perm frac |",
             "|---|---|---|---|---|---|"]
    for s in splits:
        rs = by_split[s]
        ff = np.array([float(r["flood_frac"]) for r in rs]); pf = np.array([float(r["perm_frac"]) for r in rs])
        lines.append(f"| {s} | {len({r['event'] for r in rs})} | {len(rs)} | {(ff > 0.01).mean():.2f} | "
                     f"{ff.mean():.3f} | {pf.mean():.3f} |")
    lines += ["", "Samples per event: " + ", ".join(f"{k}: {v}" for k, v in sorted(Counter((r['split'], r['event']) for r in rows).items())),
              "", "Latitude range: " + f"{min(float(r['lat']) for r in rows):.1f} .. {max(float(r['lat']) for r in rows):.1f}",
              "", "![qa](P2.3_qa.png)"]
    (OUT / "P2.3_qa.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

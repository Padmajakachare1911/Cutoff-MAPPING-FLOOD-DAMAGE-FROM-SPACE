"""E1 / E2 / E8 on Kuro Siwo held-out events (P2.11). Check-only script: never imported by src/.

    python eval/kuro_eval.py --split test --models b0 C:/cutoff_data/runs/p7/p7.pt C:/cutoff_data/runs/b2_post_only/b2_post_only.pt
    python eval/kuro_eval.py --split val  --models C:/cutoff_data/runs/p7/p7.pt --calibration      # E8

E1: per-event flood precision / recall / F1 / IoU (+ pooled) per model, official test events.
E2: the same split by slope stratum (0-5, 5-15, >=15 deg; slope from the Kuro Siwo DEM at true
    ground spacing); support px reported because steep strata are small in this lowland-heavy dataset.
E8: expected calibration error of the predicted class, before (T = 1) and after temperature scaling.
B0 note: on 224 px patches the Otsu threshold is computed per patch (in the pipeline it is per scene).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cutoff.contracts import IGNORE_INDEX  # noqa: E402
from cutoff.data.kuro_siwo import KuroSiwoDataset  # noqa: E402
from cutoff.ml.metrics import ConfusionMeter, StratifiedMeter, expected_calibration_error  # noqa: E402


def _iter_b0(ds):
    from cutoff.ml.baselines import b0_proba
    for i in range(len(ds)):
        x, y = ds.raw(i)
        yield i, b0_proba(x), y, x[6]


def _iter_ckpt(ds_raw, ckpt, device, T_override=None):
    import torch

    from cutoff.ml.model import load_checkpoint
    model, meta = load_checkpoint(ckpt, device=device)
    ds = KuroSiwoDataset(ds_raw.root, ds_raw.rows[0]["split"], meta["mean"], meta["std"],
                         zero_channels=meta.get("zero_channels", []), events=ds_raw.events)
    T = meta["temperature"] if T_override is None else T_override
    with torch.no_grad():
        for i in range(len(ds)):
            x, y = ds[i]
            with torch.autocast(device_type="cuda", enabled=device == "cuda"):
                z = model(x[None].to(device))
            p = torch.softmax(z.float() / T, 1)[0].cpu().numpy()
            yield i, p, y.numpy(), ds_raw.raw(i)[0][6]


def _iter_b1(ds, path, order, device):
    from b1_snunet import load_snunet, snunet_proba

    from cutoff.data.kuro_siwo import load_sample
    model = load_snunet(path, device)
    for i in range(len(ds)):
        x, y = ds.raw(i)
        rec = load_sample(ds.root / ds.rows[i]["path"])
        yield i, snunet_proba(model, rec, order, device), y, x[6]


def evaluate(ds, model_spec: str, device: str = "cpu", tau: float | None = None) -> dict:
    """Return {"name", "tau", "pooled", "per_event": [...], "strata": [...]} for one model.

    model_spec: "b0" | "b1:<snunet weights>[:pre_post|post_pre]" | <Cutoff checkpoint path>."""
    from cutoff.ml.model import load_checkpoint
    if model_spec == "b0":
        it, name, tau = _iter_b0(ds), "b0", 0.5 if tau is None else tau
    elif model_spec.startswith("b1:"):
        rest = model_spec[3:]
        order = "pre_post"
        if rest.endswith((":pre_post", ":post_pre")):
            rest, order = rest.rsplit(":", 1)
        it, name, tau = _iter_b1(ds, rest, order, device), f"b1_snunet_{order}", 0.5 if tau is None else tau
    else:
        meta = load_checkpoint(model_spec)[1]
        it, name = _iter_ckpt(ds, model_spec, device), Path(model_spec).stem
        tau = meta["flood_threshold"] if tau is None else tau
    sm = StratifiedMeter()
    for i, p, y, slope in it:
        pred = np.argmax(np.nan_to_num(p, nan=0.0), axis=0)
        pred = np.where(np.nan_to_num(p[2]) >= tau, 2, np.where(pred == 2, 0, pred))  # flood decided by tau
        sm.update(ds.rows[i]["event"], pred, y, slope)
    rows = sm.table()
    per_event = [r for r in rows if r["slope_bin"] == "all" and r["event"] != "ALL"]
    strata = [r for r in rows if r["slope_bin"] != "all"]
    pooled = next(r for r in rows if r["event"] == "ALL" and r["slope_bin"] == "all")
    return {"name": name, "tau": tau, "pooled": pooled, "per_event": per_event, "strata": strata,
            "split": ds.rows[0]["split"], "n_samples": len(ds)}


def calibration(ds, ckpt: str, device: str = "cpu") -> dict:
    """E8 on validation events, at T = 1 and at the checkpoint's fitted T:
    - all-class ECE of the predicted class (dominated by easy 'no water' pixels, so near 0);
    - flood ECE: is p(flood) = 0.8 really flood 80 % of the time? (the meaningful one for responders),
      computed over pixels where the model gives p(flood) >= 0.05 or that are flood."""
    from cutoff.ml.model import load_checkpoint
    T = load_checkpoint(ckpt)[1]["temperature"]
    out = {"T": T}
    for label, t in (("T=1", 1.0), ("fitted T", T)):
        conf, corr, pf, isf = [], [], [], []
        for _, p, y, _ in _iter_ckpt(ds, ckpt, device, T_override=t):
            v = y != IGNORE_INDEX
            conf.append(p.max(0)[v][::16]); corr.append((p.argmax(0) == y)[v][::16])
            rel = v & ((p[2] >= 0.05) | (y == 2))
            pf.append(p[2][rel][::4]); isf.append((y == 2)[rel][::4])
        out[f"all-class ECE, {label}"] = expected_calibration_error(np.concatenate(conf), np.concatenate(corr))
        out[f"flood ECE, {label}"] = expected_calibration_error(np.concatenate(pf), np.concatenate(isf))
    return {"name": Path(ckpt).stem, "ece": out}


def _fmt(v):
    return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.3f}"


def to_markdown(results: list[dict], calib: list[dict] | None = None) -> str:
    lines = ["## E1 - pooled flood-class scores", "", "| model | split | n | tau | precision | recall | F1 | IoU |",
             "|---|---|---|---|---|---|---|---|"]
    for r in results:
        p = r["pooled"]
        lines.append(f"| {r['name']} | {r['split']} | {r['n_samples']} | {r['tau']} | {_fmt(p['precision'])} | "
                     f"{_fmt(p['recall'])} | {_fmt(p['f1'])} | {_fmt(p['iou'])} |")
    lines += ["", "## E1 - per event (flood IoU / F1, support px)", "",
              "| event | " + " | ".join(r["name"] for r in results) + " |", "|---|" + "---|" * len(results)]
    events = sorted({e["event"] for r in results for e in r["per_event"]}, key=lambda e: (len(e), e))
    for ev in events:
        cells = []
        for r in results:
            e = next((x for x in r["per_event"] if x["event"] == ev), None)
            cells.append(f"{_fmt(e['iou'])} / {_fmt(e['f1'])} ({e['support_px']})" if e else "-")
        lines.append(f"| {ev} | " + " | ".join(cells) + " |")
    lines += ["", "## E2 - by slope stratum (all events pooled; IoU, support px)", "",
              "| slope bin | " + " | ".join(r["name"] for r in results) + " |", "|---|" + "---|" * len(results)]
    for b, lab in ((0, "0-5 deg"), (1, "5-15 deg"), (2, ">=15 deg")):
        cells = []
        for r in results:
            s = next((x for x in r["strata"] if x["event"] == "ALL" and x["slope_bin"] == b), None)
            cells.append(f"{_fmt(s['iou'])} ({s['support_px']})" if s else "-")
        lines.append(f"| {lab} | " + " | ".join(cells) + " |")
    if calib:
        cols = list(calib[0]["ece"])
        lines += ["", "## E8 - expected calibration error (validation events; T = each model's fitted temperature)", "",
                  "| model | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
        for c in calib:
            lines.append(f"| {c['name']} | " + " | ".join(_fmt(v) for v in c["ece"].values()) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(os.environ.get("CUTOFF_DATA_DIR", "C:/cutoff_data")) / "kuro"))
    ap.add_argument("--split", default="test", choices=["val", "test"])
    ap.add_argument("--models", nargs="+", default=["b0"])
    ap.add_argument("--calibration", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "docs" / "results"))
    a = ap.parse_args()
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    ds = KuroSiwoDataset(a.data, a.split, np.zeros(7), np.ones(7))
    results = [evaluate(ds, m, device) for m in a.models]
    calib = ([calibration(ds, m, device) for m in a.models if m != "b0" and not m.startswith("b1:")]
             if a.calibration else None)                     # E8 applies to our checkpoints only
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    tag = f"kuro_{a.split}"
    (out / f"{tag}.json").write_text(json.dumps({"results": results, "calibration": calib}, default=float, indent=1))
    md = to_markdown(results, calib)
    (out / f"{tag}.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()

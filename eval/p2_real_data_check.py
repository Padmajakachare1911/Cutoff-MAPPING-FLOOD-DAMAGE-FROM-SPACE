"""P2 real-data check (C2 open item): describe one pipeline run folder produced with model-v1. CHECK ONLY.

Nothing here feeds back into the model, tau, T or the rules: thresholds are frozen. No EMS/reference data is read.
For a run folder containing the s1, terrain, (s2), model, disturbance, gating and vectorize outputs, it reports:
  1. input radiometry vs the model's Kuro Siwo training statistics (per-channel mean offset in training std units),
     over all valid pixels and over flat lowland pixels (slope < 5 deg, HAND < 30 m), where Kuro Siwo lives;
  2. the model score p_flood: share >= tau, area, and its distribution in the valley-floor corridor (HAND <= 10 m);
  3. agreement with Sentinel-2 MNDWI water where S2 is clear (S2 is a pipeline input, never a label; its date
     differs from the S1 post date, so this is a plausibility check, not a score);
  4. a quick-look PNG (VV post dB, dVV dB, p_flood, hazard class, S2 water).
Usage:  python eval/p2_real_data_check.py <run_dir> [<run_dir> ...] --out docs/results/raw/P2_real_data.json --png-dir docs/plan/reports
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cutoff.contracts import CHANNELS  # noqa: E402
from cutoff.geo.sar import build_input_stack  # noqa: E402


def _read(run: Path, name: str):
    import rasterio
    p = run / f"{name}.tif"
    if not p.exists():
        return None
    with rasterio.open(p) as r:
        a = r.read()
        px_area = abs(r.transform.a * r.transform.e)
    return (a[0] if a.shape[0] == 1 else a), px_area


def _q(a, qs=(5, 25, 50, 75, 95)):
    a = a[np.isfinite(a)]
    return {f"p{q}": round(float(np.percentile(a, q)), 3) for q in qs} if a.size else None


def describe(run: Path, meta: dict) -> dict:
    pre, px_area = _read(run, "s1_pre_mean")
    post, _ = _read(run, "s1_post")
    slope, _ = _read(run, "slope")
    hand, _ = _read(run, "hand")
    pm, _ = _read(run, "p_model")
    hz, _ = _read(run, "hazard_class")
    returns = json.loads((run / "stage_returns.json").read_text(encoding="utf-8"))["returns"] \
        if (run / "stage_returns.json").exists() else {}
    tau = float(returns.get("model", {}).get("flood_threshold", meta["flood_threshold"]))
    x = build_input_stack(pre, post, slope)
    valid = np.all(np.isfinite(x[:6]), axis=0)
    lowland = valid & (slope < 5) & (hand < 30)
    mean, std = np.asarray(meta["mean"]), np.asarray(meta["std"])
    radiometry = {}
    for name, m in (("all_valid", valid), ("lowland_slope<5_hand<30", lowland)):
        if not m.any():
            radiometry[name] = None
            continue
        radiometry[name] = {"n_px": int(m.sum()), "channels": {
            CHANNELS[c]: {"mean": round(float(x[c][m].mean()), 3), "train_mean": round(float(mean[c]), 3),
                          "offset_in_train_std": round(float((x[c][m].mean() - mean[c]) / std[c]), 2)}
            for c in range(6)}}
    pf, pp = pm[2], pm[1]
    pvalid = np.isfinite(pf)
    corridor = pvalid & (hand <= 10)
    out = {"run": run.name, "tau": tau, "pixel_area_m2": px_area, "grid_px": int(pf.size),
           "valid_frac": round(float(valid.mean()), 4), "lowland_frac": round(float(lowland.mean()), 4),
           "radiometry": radiometry,
           "p_flood": {"share_ge_tau": round(float((pf[pvalid] >= tau).mean()), 6),
                       "area_ge_tau_km2": round(float((pf[pvalid] >= tau).sum() * px_area / 1e6), 3),
                       "quantiles_all": _q(pf), "max": round(float(np.nanmax(pf)), 3)},
           "corridor_hand_le_10m": {"n_px": int(corridor.sum()),
                                    "area_km2": round(float(corridor.sum() * px_area / 1e6), 3),
                                    "p_flood_quantiles": _q(pf[corridor]) if corridor.any() else None,
                                    "share_ge_tau": round(float((pf[corridor] >= tau).mean()), 4)
                                    if corridor.any() else None},
           "hazard_class_km2": {str(k): round(float((hz == k).sum() * px_area / 1e6), 3)
                                for k in (1, 2, 3, 4, 5, 254)},
           # size of the proposed gating change (not applied): class 5 on terrain where rule 3 already demotes floods
           "permanent_on_steep_or_high_hand_km2": round(float(
               ((hz == 5) & ((np.nan_to_num(slope) > 15.0) | (np.nan_to_num(hand) > 30.0))).sum() * px_area / 1e6), 3),
           "stage_returns": returns}
    s2w, s2c = _read(run, "s2_water"), _read(run, "s2_clear")
    if s2w is not None and s2c is not None:
        w, c = s2w[0], s2c[0]
        clear = (c == 1) & pvalid
        water = clear & (w == 1)
        mw = clear & ((pf >= tau) | (pp >= tau))          # model says water (flood or permanent)
        mf = clear & (pf >= tau)
        tp = int((mw & water).sum())
        out["s2_check"] = {"clear_frac": round(float(clear.mean()), 4),
                           "s2_water_km2": round(float(water.sum() * px_area / 1e6), 3),
                           "model_water_km2_in_clear": round(float(mw.sum() * px_area / 1e6), 3),
                           "model_flood_km2_in_clear": round(float(mf.sum() * px_area / 1e6), 3),
                           "share_of_s2_water_model_calls_water": round(tp / max(int(water.sum()), 1), 4),
                           "share_of_model_water_s2_calls_water": round(tp / max(int(mw.sum()), 1), 4),
                           "p_flood_quantiles_on_s2_water": _q(pf[water]) if water.any() else None}
    return out, (x, pf, hz, s2w[0] if s2w is not None else None, s2c[0] if s2c is not None else None, tau)


def quicklook(run: Path, arrays, png: Path, model_version: str, step: int = 3):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    x, pf, hz, s2w, s2c, tau = arrays
    s = (slice(None, None, step), slice(None, None, step))
    n = 5 if s2w is not None else 4
    fig, ax = plt.subplots(1, n, figsize=(4 * n, 5.2), constrained_layout=True)
    im = ax[0].imshow(x[2][s], cmap="gray", vmin=-25, vmax=0); ax[0].set_title("VV post (dB)")
    fig.colorbar(im, ax=ax[0], shrink=0.6)
    im = ax[1].imshow(x[4][s], cmap="RdBu", vmin=-6, vmax=6); ax[1].set_title("dVV post - pre (dB)")
    fig.colorbar(im, ax=ax[1], shrink=0.6)
    im = ax[2].imshow(pf[s], cmap="magma", vmin=0, vmax=1); ax[2].set_title(f"p_flood score (tau={tau})")
    fig.colorbar(im, ax=ax[2], shrink=0.6)
    h = hz[s].astype(float)
    cmap = ListedColormap(["#f0f0f0", "#08306b", "#6baed6", "#31a354", "#e6550d", "#9e9ac8", "#000000"])
    codes = np.select([h == 0, h == 1, h == 2, h == 3, h == 4, h == 5, h == 254], range(7), 0)
    ax[3].imshow(codes, cmap=cmap, vmin=0, vmax=6, interpolation="nearest")
    ax[3].set_title("hazard class\n1 dark blue, 2 light blue, 3 green, 4 orange,\n5 permanent (lilac), 254 black")
    if s2w is not None:
        v = np.where(s2c[s] != 1, np.nan, s2w[s].astype(float))
        ax[4].imshow(v, cmap=ListedColormap(["#f0f0f0", "#2171b5"]), vmin=0, vmax=1, interpolation="nearest")
        ax[4].set_title("S2 MNDWI water (blank = not clear)")
    for a in ax:
        a.set_xticks([]); a.set_yticks([])
    fig.suptitle(f"{run.name}: model {model_version} (check only, nothing tuned)")
    fig.savefig(png, dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--model", default=str(ROOT / "models" / "cutoff_unet_v1.pt"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--png-dir", default=None)
    a = ap.parse_args()
    from cutoff.ml.model import load_checkpoint
    meta = load_checkpoint(a.model)[1]
    res = []
    for r in a.runs:
        run = Path(r)
        d, arrays = describe(run, meta)
        res.append(d)
        if a.png_dir:
            quicklook(run, arrays, Path(a.png_dir) / f"P2_real_{run.name}.png",
                      d["stage_returns"].get("model", {}).get("model_version", "?"))
        print(json.dumps({k: d[k] for k in ("run", "p_flood", "corridor_hand_le_10m", "hazard_class_km2")}, indent=1))
        if "s2_check" in d:
            print(json.dumps(d["s2_check"], indent=1))
    Path(a.out).write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()

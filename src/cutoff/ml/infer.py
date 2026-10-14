"""Stage `model`: 7-channel same-track input -> calibrated 3-class probabilities. Owner: P2.

Tiled inference (224 px tiles, 64 px overlap, Hann-window blending) keeps memory bounded and
removes tile seams. Pixels with any non-finite input channel get NaN probabilities (D5), which
gating turns into "no valid observation". `ctx.model_path == "b0"` runs the non-learned baseline
so the pipeline works before training finishes.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from cutoff.geo import raster_io
from cutoff.geo.sar import build_input_stack
from cutoff.runctx import RunContext


def _weights(tile: int) -> np.ndarray:
    w = np.hanning(tile + 2)[1:-1].astype(np.float32)
    return np.outer(w, w) + 1e-3


def predict_proba(model, x_norm: np.ndarray, tile: int = 224, overlap: int = 64, temperature: float = 1.0,
                  batch: int = 8, device: str = "cpu") -> np.ndarray:
    """x_norm: (C, H, W) normalised input (NaN allowed) -> (3, H, W) float32 softmax(z / T)."""
    import torch

    if x_norm.ndim != 3:
        raise ValueError("x_norm must be (C, H, W)")
    C, H, W = x_norm.shape
    invalid = ~np.isfinite(x_norm).all(axis=0)
    x = np.nan_to_num(x_norm, nan=0.0, posinf=0.0, neginf=0.0)
    ph, pw = max(0, tile - H), max(0, tile - W)
    if ph or pw:
        x = np.pad(x, ((0, 0), (0, ph), (0, pw)), mode="reflect" if min(H, W) > max(ph, pw) else "constant")
    Hp, Wp = x.shape[1:]
    step = tile - overlap
    ys = list(range(0, Hp - tile + 1, step))
    xs = list(range(0, Wp - tile + 1, step))
    if ys[-1] != Hp - tile:
        ys.append(Hp - tile)
    if xs[-1] != Wp - tile:
        xs.append(Wp - tile)
    acc = np.zeros((3, Hp, Wp), np.float32)
    wsum = np.zeros((Hp, Wp), np.float32)
    wt = _weights(tile)
    coords = [(r, c) for r in ys for c in xs]
    model = model.to(device).eval()
    use_amp = device.startswith("cuda")
    with torch.no_grad():
        for i in range(0, len(coords), batch):
            cb = coords[i:i + batch]
            xb = torch.from_numpy(np.stack([x[:, r:r + tile, c:c + tile] for r, c in cb])).to(device)
            with torch.autocast(device_type="cuda", enabled=use_amp):
                logits = model(xb)
            pb = torch.softmax(logits.float() / float(temperature), 1).cpu().numpy()
            for (r, c), p in zip(cb, pb):
                acc[:, r:r + tile, c:c + tile] += p * wt
                wsum[r:r + tile, c:c + tile] += wt
    probs = (acc / wsum)[:, :H, :W]
    probs[:, invalid] = np.nan
    return probs


def build_stack(ctx: RunContext) -> np.ndarray:
    pre = raster_io.read(ctx, "s1_pre_mean", squeeze=False)
    post = raster_io.read(ctx, "s1_post", squeeze=False)
    slope = raster_io.read(ctx, "slope")
    return build_input_stack(pre, post, slope)


def stage_model(ctx: RunContext) -> dict:
    """Reads: s1_pre_mean.tif, s1_post.tif, slope.tif. Writes: p_model.tif.

    Returns: {"model_version": str, "flood_threshold": float, "temperature": float}
    """
    x = build_stack(ctx)
    mp = ctx.model_path or ctx.cfg.get("model", {}).get("checkpoint", "models/cutoff_unet_v1.pt")
    if mp == "b0":
        from cutoff.ml.baselines import b0_proba

        probs = b0_proba(x)
        out = {"model_version": "b0", "flood_threshold": 0.5, "temperature": 1.0}
    else:
        import torch

        from cutoff.ml.model import load_checkpoint

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model, meta = load_checkpoint(mp, device=device)
        mean = np.asarray(meta["mean"], np.float32)[:, None, None]
        std = np.asarray(meta["std"], np.float32)[:, None, None]
        xn = (x - mean) / (std + 1e-6)
        zero = list(meta.get("zero_channels", [])) or ([] if meta.get("use_slope", True) else [6])
        if 6 not in zero:
            xn[6] = np.nan_to_num(xn[6], nan=0.0)   # missing slope (no DEM) -> training mean, as in training
        for c in zero:                              # ablation channels held at their training mean, as in training
            xn[c] = np.where(np.isfinite(xn[c]), 0.0, np.nan) if c < 6 else 0.0
        cfg = ctx.cfg.get("model", {})
        probs = predict_proba(model, xn, tile=cfg.get("tile", 224), overlap=cfg.get("overlap", 64),
                              temperature=meta["temperature"], batch=cfg.get("batch", 8), device=device)
        out = {"model_version": Path(mp).name, "flood_threshold": float(meta["flood_threshold"]),
               "temperature": float(meta["temperature"])}
    raster_io.write(ctx, "p_model", probs, tags={"model_version": out["model_version"]})
    ctx.log("model", **out)
    return out

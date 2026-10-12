"""Training: event-level validation, early stopping on validation flood IoU, AMP, resume,
temperature scaling + flood threshold chosen on VALIDATION events. Owner: P2.

    python -m cutoff.ml.train --config configs/train_unet.yaml [--name p7] [--resume]

Writes <out>/last.pt (full training state, every epoch), <out>/best_state.pt, <out>/history.json,
<out>/stats.json and the deliverable checkpoint <out>/<name>.pt (contract meta, 05_contracts.md s5).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from cutoff.contracts import CHANNELS, CONTRACT_VERSION, IGNORE_INDEX, SLOPE_CLIP_DEG
from cutoff.data.kuro_siwo import KuroSiwoDataset, compute_channel_stats
from cutoff.ml.calibrate import fit_temperature
from cutoff.ml.losses import CEDiceLoss
from cutoff.ml.metrics import ConfusionMeter
from cutoff.ml.model import build_model, save_checkpoint

log = logging.getLogger("cutoff.train")
ROOT = Path(__file__).resolve().parents[3]


def seed_everything(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


@torch.no_grad()
def evaluate(model, loader, device, keep_every: int = 8):
    """Flood-class scores + a pixel subsample of logits/targets (for T and tau selection)."""
    model.eval()
    cm = ConfusionMeter(3)
    keep_l, keep_t = [], []
    for x, y in loader:
        with torch.autocast(device_type="cuda", enabled=device == "cuda"):
            logits = model(x.to(device))
        logits = logits.float().cpu()
        cm.update(logits.argmax(1).numpy(), y.numpy())
        keep_l.append(logits[:, :, ::keep_every, ::keep_every]); keep_t.append(y[:, ::keep_every, ::keep_every])
    return cm.scores(), torch.cat(keep_l), torch.cat(keep_t)


def choose_tau(logits: torch.Tensor, target: torch.Tensor, T: float) -> tuple[float, float]:
    """Flood threshold maximising flood F1 on validation pixels (after temperature scaling)."""
    p = torch.softmax(logits / T, 1)[:, 2].numpy().ravel()
    t = target.numpy().ravel()
    v = t != IGNORE_INDEX
    p, g = p[v], t[v] == 2
    best = (0.5, -1.0)
    for tau in np.arange(0.2, 0.81, 0.05):
        pred = p >= tau
        tp = (pred & g).sum(); fp = (pred & ~g).sum(); fn = (~pred & g).sum()
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best[1]:
            best = (float(round(tau, 2)), float(f1))
    return best


def train(data_root, out_dir, cfg: dict, resume: bool = False) -> Path:
    data_root, out = Path(data_root), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seed_everything(int(cfg.get("seed", 42)))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    zero = list(cfg.get("zero_channels", []))

    stats_p = out / "stats.json"
    if stats_p.exists():
        st = json.loads(stats_p.read_text()); mean, std = np.array(st["mean"]), np.array(st["std"])
    else:
        probe = KuroSiwoDataset(data_root, "train", np.zeros(7), np.ones(7))
        mean, std = compute_channel_stats(probe, max_samples=int(cfg.get("max_stat_samples", 2000)))
        stats_p.write_text(json.dumps({"mean": mean.tolist(), "std": std.tolist(), "channels": list(CHANNELS)}))
    tr = KuroSiwoDataset(data_root, "train", mean, std, augment=True, seed=int(cfg.get("seed", 42)),
                         zero_channels=zero, flips=bool(cfg.get("flips", False)))
    va = KuroSiwoDataset(data_root, "val", mean, std, zero_channels=zero)
    nw = int(cfg.get("num_workers", 2))
    tl = DataLoader(tr, batch_size=int(cfg.get("batch_size", 16)), shuffle=True, num_workers=nw, drop_last=True,
                    pin_memory=device == "cuda", persistent_workers=nw > 0)
    vl = DataLoader(va, batch_size=int(cfg.get("batch_size", 16)), shuffle=False, num_workers=nw,
                    persistent_workers=nw > 0)

    model = build_model(encoder=cfg.get("encoder", "resnet34"), pretrained=bool(cfg.get("pretrained", True))).to(device)
    epochs = int(cfg.get("epochs", 30))
    opt = torch.optim.AdamW(model.parameters(), lr=float(cfg.get("lr", 3e-4)), weight_decay=float(cfg.get("weight_decay", 1e-4)))
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda")
    loss_fn = CEDiceLoss(class_weights=tuple(cfg.get("class_weights", (1.0, 1.0, 3.0)))).to(device)
    start, best, bad, hist = 0, -1.0, 0, []
    if resume and (out / "last.pt").exists():
        ck = torch.load(out / "last.pt", map_location=device, weights_only=False)
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"]); sched.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"]); start, best, bad, hist = ck["epoch"] + 1, ck["best"], ck["bad"], ck["hist"]
        log.info("resumed at epoch %d (best val IoU %.4f)", start, best)

    for ep in range(start, epochs):
        model.train(); t0 = time.time(); run = 0.0; nb = 0
        for x, y in tl:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", enabled=device == "cuda"):
                loss = loss_fn(model(x), y)
            if not torch.isfinite(loss):
                raise FloatingPointError(f"non-finite loss at epoch {ep}; check normalisation / NaNs")
            scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            run += loss.item(); nb += 1
        sched.step()
        val, _, _ = evaluate(model, vl, device)
        rec = {"epoch": ep, "train_loss": run / max(nb, 1), "val": val, "lr": opt.param_groups[0]["lr"],
               "sec": round(time.time() - t0, 1)}
        hist.append(rec)
        log.info(json.dumps(rec, default=float))
        score = val["iou"] if np.isfinite(val["iou"]) else -1.0
        if score > best:
            best, bad = score, 0
            torch.save(model.state_dict(), out / "best_state.pt")
        else:
            bad += 1
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "sched": sched.state_dict(),
                    "scaler": scaler.state_dict(), "epoch": ep, "best": best, "bad": bad, "hist": hist}, out / "last.pt")
        (out / "history.json").write_text(json.dumps(hist, default=float, indent=1))
        if bad >= int(cfg.get("patience", 6)):
            log.info("early stop at epoch %d", ep)
            break

    model.load_state_dict(torch.load(out / "best_state.pt", map_location=device))
    val, vlog, vtgt = evaluate(model, vl, device)
    T = fit_temperature(vlog, vtgt)
    tau, f1 = choose_tau(vlog, vtgt, T)
    meta = {"channels": list(CHANNELS), "contract_version": CONTRACT_VERSION, "mean": [float(v) for v in mean],
            "std": [float(v) for v in std], "slope_clip": list(SLOPE_CLIP_DEG), "temperature": T,
            "flood_threshold": tau, "encoder": cfg.get("encoder", "resnet34"),
            "config_hash": hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(),
            "train_events": tr.events, "val_events": va.events, "git_commit": _git_commit(),
            "use_slope": 6 not in zero, "zero_channels": zero, "best_val_flood_iou": best,
            "val_scores_at_argmax": val, "val_flood_f1_at_tau": f1, "config": cfg,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    return save_checkpoint(out / f"{cfg.get('name', 'cutoff_unet')}.pt", model.cpu(), meta)


def main():
    import yaml

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs" / "train_unet.yaml"))
    ap.add_argument("--name", default=None, help="variant name from the config's `variants` block")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    cfg_all = yaml.safe_load(Path(a.config).read_text())
    cfg = dict(cfg_all["base"])
    if a.name:
        cfg.update(cfg_all["variants"][a.name])
        cfg["name"] = a.name
    data_dir = Path(os.environ.get("CUTOFF_DATA_DIR", "C:/cutoff_data"))
    out = data_dir / "runs" / cfg.get("name", "cutoff_unet")
    path = train(data_dir / "kuro", out, cfg, resume=a.resume)
    print(path)


if __name__ == "__main__":
    main()

"""B1 baseline: the released Kuro Siwo SNUNet-ECAM weights, applied zero-shot (P2.6). eval/ only.

Input format reproduced from the Kuro Siwo code (configs/train/data_config.json, dataset/Dataset.py,
training/change_detection_trainer.py, models/model_utilities.py), verified 2026-10-12:
  * each image = linear sigma0 (VV, VH), clamped to [0, 0.15] (NaN -> 0.15), then
    torchvision Normalize(mean=[0.0953, 0.0264], std=[0.0427, 0.0215]);
  * DEM appended as a 3rd channel, Normalize(mean=93.4313, std=1410.8382)  (num_channels = 2 + 1);
  * model(xA, xB): two images of the sequence; the released checkpoint's input pair is not documented,
    so `order` ("pre_post" = (pre-event 1, post-event) or "post_pre") is chosen on VALIDATION events;
  * output: 3 logits (0 no water, 1 permanent water, 2 flood), same label scheme as ours.
Weights: https://www.dropbox.com/scl/fi/3vlsveoobqe1wc71s5z2d/best_segmentation.pt (MIT, Bountos et al. 2024).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from third_party.kurosiwo_snunet import SNUNet_ECAM  # noqa: E402

CLAMP = 0.15
SAR_MEAN, SAR_STD = np.array([0.0953, 0.0264], np.float32), np.array([0.0427, 0.0215], np.float32)
DEM_MEAN, DEM_STD = 93.4313, 1410.8382


def load_snunet(path: str, device: str = "cpu") -> torch.nn.Module:
    ck = torch.load(path, map_location=device, weights_only=False)
    sd = ck.get("model_state_dict", ck)
    model = SNUNet_ECAM(3, 3, base_channel=32)
    model.load_state_dict(sd)
    return model.to(device).eval()


def _img(vv, vh, dem) -> np.ndarray:
    sar = np.stack([vv, vh]).astype(np.float32)
    sar = np.nan_to_num(np.clip(sar, 0.0, CLAMP), nan=CLAMP)
    sar = (sar - SAR_MEAN[:, None, None]) / SAR_STD[:, None, None]
    d = (np.nan_to_num(dem.astype(np.float32), nan=DEM_MEAN) - DEM_MEAN) / DEM_STD
    return np.concatenate([sar, d[None]], axis=0)


@torch.no_grad()
def snunet_proba(model, rec: dict, order: str = "pre_post", device: str = "cpu") -> np.ndarray:
    """One stored Kuro Siwo sample -> (3, H, W) softmax probabilities."""
    pre = _img(rec["vv_pre1"], rec["vh_pre1"], rec["dem"])
    post = _img(rec["vv_post"], rec["vh_post"], rec["dem"])
    a, b = (pre, post) if order == "pre_post" else (post, pre)
    ta = torch.from_numpy(a)[None].to(device)
    tb = torch.from_numpy(b)[None].to(device)
    return torch.softmax(model(ta, tb).float(), 1)[0].cpu().numpy()

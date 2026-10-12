"""U-Net (ResNet-34 encoder) for the 7-channel same-track SAR input -> 3 classes. Owner: P2.

Checkpoint = torch.save({"state_dict", "meta"}); meta keys are the contract in
docs/plan/05_contracts.md section 5. load_checkpoint refuses a checkpoint whose channel list
differs from contracts.CHANNELS, so a model can never silently see the wrong input order.
"""
from __future__ import annotations

from pathlib import Path

from cutoff.contracts import CHANNELS, N_CHANNELS

N_CLASSES = 3  # 0 no water, 1 permanent water, 2 flood (Kuro Siwo label scheme)
REQUIRED_META = {"channels", "contract_version", "mean", "std", "slope_clip", "temperature",
                 "flood_threshold", "encoder", "config_hash", "train_events", "val_events", "git_commit"}


def build_model(in_channels: int = N_CHANNELS, classes: int = N_CLASSES, encoder: str = "resnet34",
                pretrained: bool = True):
    """smp.Unet adapts the first conv when in_channels != 3 (re-uses the pretrained RGB kernels)."""
    import segmentation_models_pytorch as smp

    return smp.Unet(encoder_name=encoder, encoder_weights="imagenet" if pretrained else None,
                    in_channels=in_channels, classes=classes)


def save_checkpoint(path, model, meta: dict) -> Path:
    import torch

    missing = REQUIRED_META - set(meta)
    if missing:
        raise ValueError(f"checkpoint meta missing {sorted(missing)}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(), "meta": dict(meta)}, path)
    return path


def load_checkpoint(path, device: str = "cpu"):
    import torch

    ck = torch.load(path, map_location=device, weights_only=False)
    if not isinstance(ck, dict) or "state_dict" not in ck or "meta" not in ck:
        raise ValueError(f"{path} is not a Cutoff checkpoint")
    meta = ck["meta"]
    if list(meta.get("channels", [])) != list(CHANNELS):
        raise ValueError(f"checkpoint channels {meta.get('channels')} != contract channels {list(CHANNELS)}")
    model = build_model(in_channels=len(meta["channels"]), encoder=meta.get("encoder", "resnet34"),
                        pretrained=False)
    model.load_state_dict(ck["state_dict"])  # raises on shape mismatch
    return model.to(device).eval(), meta

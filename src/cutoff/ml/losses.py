"""Class-weighted cross-entropy + soft Dice on the flood class. Owner: P2."""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from cutoff.contracts import IGNORE_INDEX


class CEDiceLoss(nn.Module):
    def __init__(self, class_weights=(1.0, 1.0, 3.0), dice_class: int = 2, w_ce: float = 1.0, w_dice: float = 1.0):
        super().__init__()
        self.register_buffer("cw", torch.tensor(class_weights, dtype=torch.float32))
        self.dice_class, self.w_ce, self.w_dice = dice_class, w_ce, w_dice

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """logits (B, 3, H, W); target (B, H, W) int64 with IGNORE_INDEX = ignore."""
        logits = logits.float()
        ce = F.cross_entropy(logits, target, weight=self.cw.to(logits.device), ignore_index=IGNORE_INDEX)
        valid = (target != IGNORE_INDEX).float()
        p = logits.softmax(1)[:, self.dice_class] * valid
        g = (target == self.dice_class).float() * valid
        dice = 1.0 - (2 * (p * g).sum() + 1.0) / (p.sum() + g.sum() + 1.0)
        return self.w_ce * ce + self.w_dice * dice

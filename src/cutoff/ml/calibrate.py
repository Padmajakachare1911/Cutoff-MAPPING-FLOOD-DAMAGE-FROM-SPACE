"""Temperature scaling (Guo et al., ICML 2017), fitted on VALIDATION events only. Owner: P2."""
from __future__ import annotations

import torch
import torch.nn.functional as F

from cutoff.contracts import IGNORE_INDEX


def fit_temperature(logits: torch.Tensor, target: torch.Tensor, max_iter: int = 200) -> float:
    """logits (N, C, H, W), target (N, H, W) -> scalar T > 0 minimising NLL. argmax is unchanged."""
    z = logits.permute(0, 2, 3, 1).reshape(-1, logits.shape[1]).float()
    t = target.reshape(-1)
    keep = t != IGNORE_INDEX
    z, t = z[keep], t[keep]
    if t.numel() == 0:
        return 1.0
    log_t = torch.zeros(1, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=max_iter)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(z / log_t.exp(), t)
        loss.backward()
        return loss

    opt.step(closure)
    T = float(log_t.exp().item())
    return T if 0.05 < T < 20 else 1.0

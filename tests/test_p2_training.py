"""P2.3/P2.4 - Kuro Siwo dataset, stats, loss, metrics, calibration, training loop (CPU, synthetic)."""
import csv
import json

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("segmentation_models_pytorch")

from cutoff.contracts import IGNORE_INDEX  # noqa: E402
from cutoff.data import kuro_siwo as ks  # noqa: E402
from cutoff.ml.calibrate import fit_temperature  # noqa: E402
from cutoff.ml.losses import CEDiceLoss  # noqa: E402
from cutoff.ml.metrics import ConfusionMeter, StratifiedMeter, expected_calibration_error  # noqa: E402


def _rec(event, flood=True, seed=0, lat=23.0):
    rng = np.random.default_rng(seed)
    land = lambda: rng.uniform(0.05, 0.2, (224, 224))
    rec = {k: land().astype(np.float16) for k in ("vv_pre1", "vh_pre1", "vv_pre2", "vh_pre2", "vv_post", "vh_post")}
    mask = np.zeros((224, 224), np.uint8)
    if flood:
        mask[50:120, 50:150] = 2
        rec["vv_post"][50:120, 50:150] = 0.003
        rec["vh_post"][50:120, 50:150] = 0.0008
    mask[200:, :] = 1
    for k in ("vv_pre1", "vv_pre2", "vv_post"):
        rec[k][200:, :] = 0.002
    rec["mask"] = mask
    rec["dem"] = (np.arange(224)[None, :] * 1.0 + np.zeros((224, 1))).astype(np.float32)  # 1 m per pixel ramp
    valid = np.ones((224, 224), np.uint8); valid[:5, :5] = 0
    rec["valid"] = valid
    rec["meta"] = {"event": event, "aoi": "01", "flood_frac": float((mask == 2).mean()), "perm_frac": 0.1,
                   "valid_frac": 1.0, "has_dem": True, "lon": 90.0, "lat": lat, "flood_date": None}
    return rec


@pytest.fixture
def store(tmp_path):
    rows = []
    for i, (split, ev) in enumerate([("train", "130"), ("train", "130"), ("train", "470"), ("train", "470"),
                                     ("val", "514"), ("val", "514")]):
        rec = _rec(ev, flood=i % 2 == 0, seed=i)
        p = ks.save_sample(rec, tmp_path / split / ev / f"01_s{i}.npz")
        rows.append({"path": str(p.relative_to(tmp_path)), "split": split, "event": ev, "aoi": "01",
                     "sample": f"s{i}", "flood_frac": rec["meta"]["flood_frac"], "perm_frac": 0.1,
                     "valid_frac": 1.0, "has_dem": True, "lon": 90.0, "lat": 23.0})
    with (tmp_path / "index.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return tmp_path


def test_slope_uses_ground_spacing_in_web_mercator():
    rec = _rec("1", lat=60.0)        # 3857 pixel = 10 m nominal = 5 m on the ground at 60 deg
    x = ks.sample_to_input(rec)
    assert np.nanmedian(x[6]) == pytest.approx(np.degrees(np.arctan(1 / 5.0)), rel=0.02)


def test_dataset_shapes_ignore_and_normalisation(store):
    ds = ks.KuroSiwoDataset(store, "train", mean=np.zeros(7), std=np.ones(7))
    x, y = ds[0]
    assert x.shape == (7, 224, 224) and x.dtype == torch.float32 and torch.isfinite(x).all()
    assert y.shape == (224, 224) and y.dtype == torch.int64
    assert (y[:5, :5] == IGNORE_INDEX).all() and set(torch.unique(y).tolist()) <= {0, 1, 2, IGNORE_INDEX}
    assert len(ds) == 4 and ds.events == ["130", "470"]


def test_label_3_is_ignored(tmp_path):
    rec = _rec("130")
    rec["mask"][100:110, 100:110] = 3                      # Kuro Siwo 'unannotated'
    p = ks.save_sample(rec, tmp_path / "train" / "130" / "x.npz")
    with (tmp_path / "index.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "split", "event", "aoi", "sample", "flood_frac", "perm_frac",
                                          "valid_frac", "has_dem", "lon", "lat"])
        w.writeheader()
        w.writerow({"path": str(p.relative_to(tmp_path)), "split": "train", "event": "130", "aoi": "01",
                    "sample": "x", "flood_frac": 0.1, "perm_frac": 0.1, "valid_frac": 1, "has_dem": True,
                    "lon": 90, "lat": 23})
    _, y = ks.KuroSiwoDataset(tmp_path, "train", np.zeros(7), np.ones(7))[0]
    assert (y[100:110, 100:110] == IGNORE_INDEX).all() and int(y.max()) == IGNORE_INDEX and 3 not in y.unique()


def test_zero_channels_and_augmentation(store):
    ds = ks.KuroSiwoDataset(store, "train", mean=np.zeros(7), std=np.ones(7), zero_channels=[6],
                            augment=True, seed=1)
    x, _ = ds[0]
    assert torch.all(x[6] == 0)
    x2, _ = ks.KuroSiwoDataset(store, "train", mean=np.zeros(7), std=np.ones(7))[0]
    d = (x - x2)[:4]
    assert d.abs().mean() > 0                                     # augmented
    # radiometric gain is shared by pre and post -> the change channels keep their meaning
    assert torch.allclose((x[4] - x2[4]).mean(), torch.tensor(0.0), atol=0.05)


def test_channel_stats_from_train_only(store):
    ds = ks.KuroSiwoDataset(store, "train", mean=np.zeros(7), std=np.ones(7))
    mean, std = ks.compute_channel_stats(ds, max_samples=10)
    assert mean.shape == (7,) and (std > 0).all() and -30 < mean[0] < 0


def test_loss_metrics_and_ece():
    logits = torch.randn(2, 3, 16, 16, requires_grad=True)
    y = torch.randint(0, 3, (2, 16, 16)); y[0, 0, 0] = IGNORE_INDEX
    loss = CEDiceLoss()(logits, y)
    loss.backward()
    assert torch.isfinite(loss) and logits.grad is not None
    cm = ConfusionMeter(3)
    cm.update(np.array([2, 0, 2, 0, 2]), np.array([2, 2, 0, 0, IGNORE_INDEX]))
    s = cm.scores()
    assert s["iou"] == pytest.approx(1 / 3) and s["precision"] == 0.5 and s["recall"] == 0.5
    sm = StratifiedMeter()
    sm.update("e1", np.array([[2, 0]]), np.array([[2, 0]]), np.array([[1.0, 30.0]]))
    assert any(r["slope_bin"] == 2 for r in sm.table())
    assert expected_calibration_error(np.array([0.9, 0.9]), np.array([1, 1])) == pytest.approx(0.1)


def test_temperature_keeps_argmax():
    z = torch.randn(4, 3, 8, 8) * 5
    t = torch.randint(0, 3, (4, 8, 8))
    T = fit_temperature(z, t)
    assert T > 0 and torch.equal((z / T).argmax(1), z.argmax(1))


def test_overfit_tiny_batch():
    from cutoff.ml.model import build_model
    torch.manual_seed(0)
    m = build_model(encoder="resnet18", pretrained=False)
    x = torch.randn(4, 7, 64, 64)
    y = torch.zeros(4, 64, 64, dtype=torch.long); y[:, 16:48, 16:48] = 2
    opt = torch.optim.AdamW(m.parameters(), lr=3e-3)
    loss_fn = CEDiceLoss()
    m.train()
    first = None
    for _ in range(40):
        opt.zero_grad(); loss = loss_fn(m(x), y); loss.backward(); opt.step()
        first = first if first is not None else loss.item()
    assert loss.item() < 0.2 * first


def test_train_writes_checkpoint_and_resumes(store, tmp_path):
    from cutoff.ml.model import load_checkpoint
    from cutoff.ml.train import train
    cfg = {"encoder": "resnet18", "pretrained": False, "epochs": 2, "batch_size": 2, "lr": 1e-3,
           "weight_decay": 1e-4, "patience": 5, "num_workers": 0, "seed": 0, "zero_channels": [],
           "max_stat_samples": 10, "name": "unit"}
    out = tmp_path / "run"
    best = train(store, out, cfg)
    assert best.exists() and (out / "last.pt").exists()
    hist = json.loads((out / "history.json").read_text())
    assert len(hist) == 2 and "val" in hist[0] and "iou" in hist[0]["val"]
    _, meta = load_checkpoint(best)
    assert meta["train_events"] == ["130", "470"] and meta["val_events"] == ["514"]
    assert meta["temperature"] > 0 and 0 < meta["flood_threshold"] < 1
    cfg["epochs"] = 3                                     # resume continues from epoch 2
    train(store, out, cfg, resume=True)
    assert len(json.loads((out / "history.json").read_text())) == 3

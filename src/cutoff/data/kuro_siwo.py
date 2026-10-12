"""Kuro Siwo access: tar indexing over HTTP Range, sample decoding, local npz store.

Owner: P2. Verified layout (2026-10-12) of orion-ai-lab/Kuro-Siwo-GeoTIFFs, folder GRD/:
35 tars x ~20 GB (699 GB), PAX headers, members ordered by event then AOI directory:

    data/<actid>/<aoi>/[<xx>/]<sample-hash>/
        MS1_IVV_*.tif  MS1_IVH_*.tif      post-event, linear sigma0 (float32, EPSG:3857, 224x224)
        SL1_IVV/IVH_*.tif, SL2_IVV/IVH_*  pre-event 1 (closer) and 2
        MK0_MLU_*.tif   label uint8: 0 no water, 1 permanent water, 2 flood   (labelled samples only)
        MK0_MNA_*.tif   valid mask uint8 (1 = valid)
        MK0_DEM_*.tif   elevation float32 (m)
        info.json       actid, aoiid, pflood, pwater, geom, ...

AOI directory "00" with file AOI "NA" holds unlabelled samples (no MK0_MLU); they are skipped.
Instead of downloading 699 GB we probe each tar at intervals with Range requests
(`find_header`), build an index of byte segments per (event, aoi) and stream only those.
"""
from __future__ import annotations

import json
import math
import tarfile
from pathlib import Path
from typing import Iterator

import numpy as np

REPO = "orion-ai-lab/Kuro-Siwo-GeoTIFFs"
TRISHULI_LONLAT = (85.3, 28.1)
EXCLUDE_KM = 100.0
_SAR = {"MS1_IVV": "vv_post", "MS1_IVH": "vh_post", "SL1_IVV": "vv_pre1", "SL1_IVH": "vh_pre1",
        "SL2_IVV": "vv_pre2", "SL2_IVH": "vh_pre2"}


# --------------------------------------------------------------------------- tar parsing
def sample_key(path: str) -> tuple[str, str, str] | None:
    """'data/<event>/<aoi>/.../<sample>/<file>' -> (event, aoi, sample). None for non-data paths."""
    parts = path.strip("/").split("/")
    if len(parts) < 4 or parts[0] != "data":
        return None
    last = parts[-1]
    sample = parts[-2] if "." in last else last
    return parts[1], parts[2], sample


def _checksum_ok(blk: bytes) -> bool:
    try:
        stored = int(blk[148:156].split(b"\0", 1)[0].strip() or b"0", 8)
    except ValueError:
        return False
    return stored == sum(blk[:148]) + 8 * 32 + sum(blk[156:512])


def _name(blk: bytes) -> str:
    name = blk[0:100].split(b"\0", 1)[0].decode(errors="replace")
    prefix = blk[345:500].split(b"\0", 1)[0].decode(errors="replace")
    return f"{prefix}/{name}" if prefix else name


def find_header(buf: bytes, base: int) -> tuple[int, str] | None:
    """First valid tar header in `buf` (which starts at absolute byte `base`, a multiple of 512).

    Returns (absolute offset of the header record, member path). PAX extended headers are
    resolved to the real path. Offsets returned are safe starting points for a streaming
    tarfile reader.
    """
    if base % 512:
        raise ValueError("base must be 512-aligned")
    for i in range(0, len(buf) - 511, 512):
        blk = buf[i:i + 512]
        if blk[257:262] != b"ustar" or not _checksum_ok(blk):
            continue
        if blk[156:157] in (b"x", b"g"):
            size = int(blk[124:136].split(b"\0", 1)[0].strip() or b"0", 8)
            data = buf[i + 512:i + 512 + size]
            paths = [ln.split(b"path=", 1)[1] for ln in data.split(b"\n") if b"path=" in ln]
            if paths:
                return base + i, paths[0].decode(errors="replace")
            nxt = i + 512 + ((size + 511) // 512) * 512
            if nxt + 512 <= len(buf):
                return base + i, _name(buf[nxt:nxt + 512])
            return None
        return base + i, _name(blk)
    return None


def iter_samples(fileobj) -> Iterator[tuple[str, str, str, dict[str, bytes], int]]:
    """Stream a tar (from a header boundary) and yield
    (event, aoi, sample, {basename: bytes}, stream offset of the sample's first member)."""
    tf = tarfile.open(fileobj=fileobj, mode="r|")
    cur, files, first_off = None, {}, 0
    for m in tf:
        if not m.isfile():
            continue
        key = sample_key(m.name)
        if key is None:
            continue
        if key != cur:
            if cur is not None:
                yield (*cur, files, first_off)
            files, first_off = {}, m.offset
        cur = key
        files[m.name.rsplit("/", 1)[-1]] = tf.extractfile(m).read()
    if cur is not None and files:
        yield (*cur, files, first_off)


# --------------------------------------------------------------------------- decoding / storage
def _read_tif(data: bytes):
    import rasterio
    with rasterio.MemoryFile(data) as mf, mf.open() as ds:
        return ds.read(1), ds.transform, ds.crs


def _find(files: dict[str, bytes], prefix: str) -> bytes | None:
    for k, v in files.items():
        if k.startswith(prefix):
            return v
    return None


def decode_sample(files: dict[str, bytes]) -> dict | None:
    """Labelled sample -> arrays (SAR float16 linear, dem float32, mask/valid uint8) + meta.
    Returns None for unlabelled or incomplete samples."""
    from pyproj import Transformer

    if _find(files, "MK0_MLU") is None:
        return None
    rec: dict = {}
    for prefix, key in _SAR.items():
        data = _find(files, prefix)
        if data is None:
            return None
        arr, tr, crs = _read_tif(data)
        rec[key] = np.nan_to_num(arr, nan=0.0).astype(np.float16)
    dem = _find(files, "MK0_DEM")
    mna = _find(files, "MK0_MNA")
    mask, _, _ = _read_tif(_find(files, "MK0_MLU"))
    rec["mask"] = mask.astype(np.uint8)
    rec["dem"] = (_read_tif(dem)[0].astype(np.float32) if dem is not None
                  else np.full(mask.shape, np.nan, np.float32))
    valid = _read_tif(mna)[0].astype(np.uint8) if mna is not None else np.ones(mask.shape, np.uint8)
    sar_ok = (rec["vv_post"] > 0) & (rec["vv_pre1"] > 0) & (rec["vv_pre2"] > 0)
    rec["valid"] = (valid.astype(bool) & sar_ok).astype(np.uint8)
    info = json.loads(files.get("info.json", b"{}") or b"{}")
    cx, cy = tr.c + tr.a * mask.shape[1] / 2, tr.f + tr.e * mask.shape[0] / 2
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(cx, cy)
    v = rec["valid"].astype(bool)
    n = max(int(v.sum()), 1)
    rec["meta"] = {
        "event": str(info.get("actid", "")), "aoi": str(info.get("aoiid", "")),
        "flood_frac": float(((rec["mask"] == 2) & v).sum() / n),
        "perm_frac": float(((rec["mask"] == 1) & v).sum() / n),
        "valid_frac": float(v.mean()), "has_dem": dem is not None,
        "lon": float(lon), "lat": float(lat), "flood_date": info.get("flood_date"),
    }
    return rec


def save_sample(rec: dict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {k: v for k, v in rec.items() if k != "meta"}
    np.savez_compressed(path, meta=np.array(json.dumps(rec["meta"])), **arrays)
    return path


def load_sample(path: str | Path) -> dict:
    with np.load(path, allow_pickle=False) as z:
        out = {k: z[k] for k in z.files if k != "meta"}
        out["meta"] = json.loads(str(z["meta"]))
    return out


# --------------------------------------------------------------------------- model input + dataset (P2.3)
NOMINAL_PIXEL_M = 10.0   # Kuro Siwo patches: 10 m spacing in EPSG:3857 units


def sample_to_input(rec: dict) -> np.ndarray:
    """Stored sample -> unnormalised (7, H, W) model input via the SAME builder as inference.

    Web Mercator stretches distances by 1/cos(lat): a nominal 10 m pixel is 10*cos(lat) m on the
    ground, so slope uses the true ground spacing (otherwise slope is under-estimated)."""
    from cutoff.geo.sar import build_input_stack, pre_mean_linear

    f = lambda k: rec[k].astype(np.float32)
    pre = pre_mean_linear(np.stack([np.stack([f("vv_pre1"), f("vh_pre1")]), np.stack([f("vv_pre2"), f("vh_pre2")])]))
    post = np.stack([f("vv_post"), f("vh_post")])
    lat = float(rec.get("meta", {}).get("lat", 0.0))
    px = NOMINAL_PIXEL_M * max(math.cos(math.radians(lat)), 0.05)
    dem = rec["dem"].astype(np.float32)
    if np.isfinite(dem).any():
        gy, gx = np.gradient(dem, px)
        slope = np.degrees(np.arctan(np.hypot(gx, gy))).astype(np.float32)
    else:
        slope = np.full(dem.shape, np.nan, np.float32)
    return build_input_stack(pre, post, slope)


class KuroSiwoDataset:
    """torch-style dataset over the local npz store written by scripts/fetch_kuro_subset.py.

    Returns x float32 (7, 224, 224) normalised (NaN -> 0 after normalisation; `zero_channels` held
    at 0 = their training mean, used for ablations) and y int64 (224, 224), IGNORE_INDEX where the
    valid mask is 0 or any SAR channel is missing. Augmentation (train only): a radiometric gain of
    +-1 dB applied to pre AND post (so the change channels keep their meaning) + Gaussian noise
    (sigma 0.05 in normalised units) on SAR channels. No geometric flips (they mirror look geometry;
    E3 ablation only)."""

    def __init__(self, root, split: str, mean, std, augment: bool = False, seed: int = 0,
                 zero_channels=(), index_csv: str = "index.csv", events=None, flips: bool = False):
        import csv

        self.root = Path(root)
        rows = list(csv.DictReader((self.root / index_csv).open()))
        keep = set(map(str, events)) if events is not None else None
        self.rows = [r for r in rows if r["split"] == split and (keep is None or r["event"] in keep)]
        if not self.rows:
            raise ValueError(f"no samples for split={split} under {self.root}")
        self.events = sorted({r["event"] for r in self.rows}, key=lambda e: (len(e), e))
        self.mean = np.asarray(mean, np.float32)[:, None, None]
        self.std = np.asarray(std, np.float32)[:, None, None]
        self.augment, self.flips = augment, flips
        self.zero = [int(c) for c in zero_channels]
        self.rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return len(self.rows)

    def raw(self, i: int) -> tuple[np.ndarray, np.ndarray]:
        from cutoff.contracts import IGNORE_INDEX

        rec = load_sample(self.root / self.rows[i]["path"])
        x = sample_to_input(rec)
        y = rec["mask"].astype(np.int64)
        y[(rec["valid"] == 0) | ~np.isfinite(x[:6]).all(axis=0)] = IGNORE_INDEX
        return x, y

    def __getitem__(self, i: int):
        import torch

        x, y = self.raw(i)
        if self.augment:
            x[:4] += self.rng.uniform(-1.0, 1.0)                    # same dB gain on pre and post
        x = (x - self.mean) / (self.std + 1e-6)
        if self.augment:
            x[:6] += self.rng.normal(0, 0.05, size=x[:6].shape).astype(np.float32)
            if self.flips and self.rng.random() < 0.5:
                x, y = x[:, :, ::-1], y[:, ::-1]
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        for c in self.zero:
            x[c] = 0.0
        return torch.from_numpy(np.ascontiguousarray(x, np.float32)), torch.from_numpy(np.ascontiguousarray(y))


def compute_channel_stats(ds: KuroSiwoDataset, max_samples: int = 2000, seed: int = 0):
    """Per-channel mean/std over valid pixels of TRAINING samples (unnormalised dB / degrees)."""
    from cutoff.contracts import IGNORE_INDEX

    rng = np.random.default_rng(seed)
    idx = rng.choice(len(ds), size=min(max_samples, len(ds)), replace=False)
    s = np.zeros(7); ss = np.zeros(7); n = np.zeros(7)
    for i in idx:
        x, y = ds.raw(int(i))
        v = y != IGNORE_INDEX
        for c in range(7):
            xc = x[c][v & np.isfinite(x[c])].astype(np.float64)
            s[c] += xc.sum(); ss[c] += (xc ** 2).sum(); n[c] += xc.size
    n = np.maximum(n, 1)
    mean = s / n
    std = np.sqrt(np.maximum(ss / n - mean ** 2, 1e-6))
    return mean.astype(np.float32), std.astype(np.float32)


# --------------------------------------------------------------------------- geography
def km_between(lon1, lat1, lon2, lat2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def near_trishuli(lon: float, lat: float, km: float = EXCLUDE_KM) -> bool:
    return km_between(lon, lat, *TRISHULI_LONLAT) <= km


# --------------------------------------------------------------------------- tar index
def segments_from_probes(tar: str, probes: list[tuple[int, tuple[str, str]]], size: int) -> list[dict]:
    """Collapse sorted (header_offset, (event, aoi)) probes into byte segments per key.

    A segment starts at the last probe *before* its first probe (so no member of the key is
    missed; a few members of the previous key are streamed and skipped) and ends at the first
    probe after its last probe (or the tar size)."""
    probes = sorted(probes)
    segs, i = [], 0
    while i < len(probes):
        j = i
        while j + 1 < len(probes) and probes[j + 1][1] == probes[i][1]:
            j += 1
        start = probes[i - 1][0] if i > 0 else probes[i][0]
        end = probes[j + 1][0] if j + 1 < len(probes) else size
        ev, aoi = probes[i][1]
        segs.append({"tar": tar, "event": ev, "aoi": aoi, "start": start, "end": end})
        i = j + 1
    return segs

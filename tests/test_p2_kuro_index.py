"""P2.1 - Kuro Siwo tar indexing and sample decoding (offline, synthetic tars)."""
import io
import json
import tarfile

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from cutoff.data import kuro_siwo as ks

EV = "1111009"


def _tif(arr: np.ndarray) -> bytes:
    """A 224x224 GeoTIFF in EPSG:3857 like the Kuro Siwo patches (Nepal-ish location optional)."""
    prof = {"driver": "GTiff", "height": arr.shape[0], "width": arr.shape[1], "count": 1,
            "dtype": arr.dtype.name, "crs": "EPSG:3857", "transform": from_origin(1_000_000, 3_000_000, 10, 10)}
    with rasterio.MemoryFile() as mf:
        with mf.open(**prof) as ds:
            ds.write(arr, 1)
        return mf.read()


def _sample_files(labelled=True, flood_px=100, aoi="01", date="20220911"):
    rng = np.random.default_rng(0)
    sar = lambda: rng.uniform(0.01, 0.3, (224, 224)).astype(np.float32)
    files = {}
    for p in ("MS1", "SL1", "SL2"):
        for pol in ("IVV", "IVH"):
            files[f"{p}_{pol}_{EV}_{aoi}_{date}.tif"] = _tif(sar())
    files[f"MK0_DEM_{EV}_{aoi}_{date}.tif"] = _tif(rng.uniform(1000, 1500, (224, 224)).astype(np.float32))
    files[f"MK0_MNA_{EV}_{aoi}_{date}.tif"] = _tif(np.ones((224, 224), np.uint8))
    if labelled:
        m = np.zeros((224, 224), np.uint8)
        m.flat[:flood_px] = 2
        m[-1, :10] = 1
        files[f"MK0_MLU_{EV}_{aoi}_{date}.tif"] = _tif(m)
    files["info.json"] = json.dumps({"actid": int(EV), "aoiid": aoi, "pflood": 0.1, "pwater": 0.01}).encode()
    return files


def _make_tar(samples) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for folder, files in samples:
            d = tarfile.TarInfo(folder); d.type = tarfile.DIRTYPE
            tf.addfile(d)
            for name, data in files.items():
                ti = tarfile.TarInfo(f"{folder}/{name}"); ti.size = len(data)
                ti.pax_headers = {"path": f"{folder}/{name}"}   # force a PAX header like the real tars
                tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def test_sample_key_handles_both_layouts():
    assert ks.sample_key("data/1111009/00/92/92dcb5/MK0_MNA_1111009_NA_20220911.tif") == ("1111009", "00", "92dcb5")
    assert ks.sample_key("data/497/01/23c42b/MS1_IVV_497_01_20210203.tif") == ("497", "01", "23c42b")
    assert ks.sample_key("data/497/01/23c42b/") == ("497", "01", "23c42b")
    assert ks.sample_key("README.md") is None


def test_find_header_reads_pax_path_from_any_offset():
    raw = _make_tar([(f"data/{EV}/01/aaa", _sample_files()), (f"data/{EV}/01/bbb", _sample_files())])
    off, path = ks.find_header(raw, base=0)
    assert off == 0 and path.startswith(f"data/{EV}/01/aaa")
    # start in the middle of the first sample's data: the next header found must belong to a later member
    mid = (len(raw) // 2 // 512) * 512
    off2, path2 = ks.find_header(raw[mid:], base=mid)
    assert off2 >= mid and path2.startswith(f"data/{EV}/01/")
    # the reported offset is a real header: tarfile can stream from it
    tf = tarfile.open(fileobj=io.BytesIO(raw[off2:]), mode="r|")
    first = next(iter(tf))
    assert first.name.startswith(f"data/{EV}/01/")


def test_find_header_returns_none_on_pure_data():
    assert ks.find_header(b"\x00" * 4096 + b"x" * 4096, base=0) is None


def test_iter_and_decode_samples():
    raw = _make_tar([(f"data/{EV}/00/92/unl", _sample_files(labelled=False, aoi="NA")),
                     (f"data/{EV}/01/aaa", _sample_files(flood_px=500)),
                     (f"data/{EV}/01/bbb", _sample_files(flood_px=0))])
    got = list(ks.iter_samples(io.BytesIO(raw)))
    assert [g[:3] for g in got] == [(EV, "00", "unl"), (EV, "01", "aaa"), (EV, "01", "bbb")]
    assert ks.decode_sample(got[0][3]) is None                      # unlabelled -> skipped
    rec = ks.decode_sample(got[1][3])
    assert rec["vv_post"].dtype == np.float16 and rec["vv_post"].shape == (224, 224)
    assert rec["dem"].dtype == np.float32                            # DEM kept float32 (slope precision)
    assert rec["mask"].dtype == np.uint8 and set(np.unique(rec["mask"])) <= {0, 1, 2}
    assert rec["meta"]["event"] == EV and rec["meta"]["flood_frac"] == pytest.approx(500 / 224**2)
    assert -180 <= rec["meta"]["lon"] <= 180 and -90 <= rec["meta"]["lat"] <= 90


def test_npz_roundtrip(tmp_path):
    rec = ks.decode_sample(_sample_files())
    p = ks.save_sample(rec, tmp_path / "x.npz")
    back = ks.load_sample(p)
    assert np.array_equal(back["mask"], rec["mask"]) and back["meta"]["event"] == EV
    assert np.allclose(back["vv_pre1"].astype(np.float32), rec["vv_pre1"].astype(np.float32))


def test_distance_exclusion():
    assert ks.km_between(85.3, 28.1, 85.3, 28.1) == pytest.approx(0.0)
    assert ks.km_between(85.3, 28.1, 86.3, 28.1) == pytest.approx(98.1, rel=0.02)
    assert ks.near_trishuli(85.5, 28.2) and not ks.near_trishuli(90.0, 23.7)


def test_segments_from_probes():
    # probes along one tar: (header_offset, key)
    probes = [(0, ("1", "00")), (100, ("1", "00")), (200, ("1", "01")), (300, ("1", "01")), (400, ("2", "01"))]
    segs = ks.segments_from_probes("GRD/00000.tar", probes, size=500)
    by_key = {(s["event"], s["aoi"]): s for s in segs}
    # a segment starts at the last probe BEFORE its first probe (safe: may include a little of the previous key)
    assert by_key[("1", "01")]["start"] == 100 and by_key[("1", "01")]["end"] == 400
    assert by_key[("1", "00")]["start"] == 0
    assert by_key[("2", "01")]["start"] == 300 and by_key[("2", "01")]["end"] == 500

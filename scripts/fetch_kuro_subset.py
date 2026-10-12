"""Fetch a Kuro Siwo GRD subset without downloading the 699 GB archive (P2.1).

    python scripts/fetch_kuro_subset.py index            # ~10 min: Range-probe all 35 tars -> segment index
    python scripts/fetch_kuro_subset.py fetch            # stream only the needed segments -> npz + index.csv
    python scripts/fetch_kuro_subset.py fetch --splits val test --dry-run

Data go to $CUTOFF_DATA_DIR/kuro (default C:/cutoff_data/kuro), outside the git repo.
Resumable: samples already on disk are skipped; finished (event, aoi, split) units are logged.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cutoff.data import kuro_siwo as ks  # noqa: E402

DATA = Path(os.environ.get("CUTOFF_DATA_DIR", "C:/cutoff_data")) / "kuro"
SEG_INDEX = ROOT / "configs" / "kuro_grd_segments.json"
CSV_FIELDS = ["path", "split", "event", "aoi", "sample", "flood_frac", "perm_frac", "valid_frac",
              "has_dem", "lon", "lat"]
_tls = threading.local()


def session() -> requests.Session:
    """One HTTP session per thread (requests.Session is not thread-safe)."""
    if not hasattr(_tls, "s"):
        _tls.s = requests.Session()
    return _tls.s


def resolve(tar: str) -> tuple[str, int]:
    from huggingface_hub import hf_hub_url
    url = hf_hub_url(ks.REPO, tar, repo_type="dataset")
    for attempt in range(5):
        try:
            h = session().head(url, allow_redirects=True, timeout=60)
            h.raise_for_status()
            return h.url, int(h.headers["content-length"])
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"cannot resolve {tar}")


def probe(url: str, off: int, span: int = 2 * 1024 * 1024) -> tuple[int, tuple[str, str]] | None:
    start = (off // 512) * 512
    for attempt in range(5):
        try:
            r = session().get(url, headers={"Range": f"bytes={start}-{start + span - 1}"}, timeout=60)
            r.raise_for_status()
            buf = r.content
            pos = 0
            while pos < len(buf):
                hit = ks.find_header(buf[pos:], start + pos)
                if hit is None:
                    return None
                hoff, path = hit
                key = ks.sample_key(path)
                if key is not None:
                    return hoff, key[:2]
                pos = hoff - start + 512
            return None
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def index_tar(tar: str, step: int, tol: int) -> tuple[list[dict], list]:
    url, size = resolve(tar)
    offs = list(range(0, size, step)) + [max(size - 4 * 1024 * 1024, 0)]
    with ThreadPoolExecutor(8) as ex:
        coarse = [p for p in ex.map(lambda o: probe(url, o), offs) if p]
    probes = sorted(set(coarse))

    def refine(a, b):
        if b[0] - a[0] <= tol or a[1] == b[1]:
            return
        mid = probe(url, (a[0] + b[0]) // 2)
        if mid is None or mid[0] in (a[0], b[0]):
            return
        probes.append(mid)
        refine(a, mid)
        refine(mid, b)

    for a, b in zip(sorted(coarse), sorted(coarse)[1:]):
        refine(a, b)
    probes = sorted(set(probes))
    return ks.segments_from_probes(tar, probes, size), probes


def cmd_index(args):
    from huggingface_hub import HfApi
    tars = sorted(i.path for i in HfApi().list_repo_tree(ks.REPO, path_in_repo="GRD", repo_type="dataset")
                  if i.path.endswith(".tar"))
    out = {"repo": ks.REPO, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "segments": []}
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for tar, (segs, probes) in zip(tars, ex.map(lambda t: index_tar(t, args.step, args.tol), tars)):
            out["segments"] += segs
            print(f"{tar}: {len(probes)} probes, {len(segs)} segments "
                  f"{sorted({(s['event'], s['aoi']) for s in segs})} [{time.time()-t0:.0f}s]", flush=True)
    SEG_INDEX.write_text(json.dumps(out, indent=1))
    print("wrote", SEG_INDEX)


class _Counting:
    def __init__(self, raw):
        self.raw, self.n = raw, 0

    def read(self, k=-1):
        b = self.raw.read(k)
        self.n += len(b)
        return b


def stream_segment(seg, url, start, quota_fn, on_sample, max_bytes):
    """Stream [start, seg.end) and feed matching samples to on_sample until quota_fn() is False."""
    r = session().get(url, headers={"Range": f"bytes={start}-{seg['end'] - 1}"}, stream=True, timeout=120)
    r.raise_for_status()
    r.raw.decode_content = True
    cnt = _Counting(r.raw)
    seen = False
    last_off = 0
    try:
        for ev, aoi, sid, files, rel in ks.iter_samples(cnt):
            last_off = rel
            if (ev, aoi) != (seg["event"], seg["aoi"]):
                if seen:
                    break
                continue
            seen = True
            on_sample(ev, aoi, sid, files)
            if not quota_fn() or cnt.n > max_bytes:
                break
    except Exception as e:  # truncated tail at seg end, or connection drop
        if not isinstance(e, (EOFError,)) and "unexpected end" not in str(e):
            r.close()
            return cnt.n, start + last_off, e
    r.close()
    return cnt.n, None, None


def cmd_fetch(args):
    splits = yaml.safe_load((ROOT / "configs" / "kuro_siwo_splits.yaml").read_text())
    segs = json.loads(SEG_INDEX.read_text())["segments"]
    DATA.mkdir(parents=True, exist_ok=True)
    csv_path = DATA / "index.csv"
    have = set()
    counts: dict[tuple[str, str], dict] = {}
    if csv_path.exists():
        for row in csv.DictReader(csv_path.open()):
            have.add(row["sample"])
            c = counts.setdefault((row["split"], row["event"]), {"n": 0, "flood": 0})
            c["n"] += 1
            c["flood"] += float(row["flood_frac"]) > 0.01
    new_csv = not csv_path.exists()
    fcsv = csv_path.open("a", newline="")
    w = csv.DictWriter(fcsv, fieldnames=CSV_FIELDS)
    if new_csv:
        w.writeheader()
    quota = {"val": args.val_per_event, "test": args.test_per_event, "train": args.train_per_event}
    lock = threading.Lock()                     # guards the CSV writer, `have` and the totals
    tot = {"excluded": 0, "bytes": 0}

    def fetch_event(split: str, ev: str) -> None:
        ev_segs = [s for s in segs if s["event"] == ev and s["aoi"] != "00"]
        c = counts.setdefault((split, ev), {"n": 0, "flood": 0})
        q = quota[split]
        q_flood = math.ceil(q * args.train_flood_share) if split == "train" else 0
        gb = sum(s["end"] - s["start"] for s in ev_segs) / 1e9
        print(f"[{split}] event {ev}: {len(ev_segs)} segments ~{gb:.1f} GB raw, have {c['n']}/{q}", flush=True)
        if args.dry_run or c["n"] >= q or not ev_segs:
            return

        def want_more():
            return c["n"] < q

        def on_sample(e, aoi, sid, files):
            if sid in have or c["n"] >= q:
                return
            rec = ks.decode_sample(files)
            if rec is None:
                return
            m = rec["meta"]
            if ks.near_trishuli(m["lon"], m["lat"]):
                with lock:
                    tot["excluded"] += 1
                return
            is_flood = m["flood_frac"] > 0.01
            if split == "train" and not is_flood and (c["n"] - c["flood"]) >= q - q_flood:
                return  # keep >= train_flood_share of train samples with flood pixels
            p = ks.save_sample(rec, DATA / split / e / f"{aoi}_{sid}.npz")
            with lock:
                have.add(sid)
                c["n"] += 1
                c["flood"] += is_flood
                w.writerow({"path": str(p.relative_to(DATA)), "split": split, "event": e, "aoi": aoi,
                            "sample": sid, "flood_frac": round(m["flood_frac"], 5),
                            "perm_frac": round(m["perm_frac"], 5), "valid_frac": round(m["valid_frac"], 4),
                            "has_dem": m["has_dem"], "lon": round(m["lon"], 5), "lat": round(m["lat"], 5)})
                if c["n"] % 50 == 0:
                    fcsv.flush()
                    print(f"   {split}/{e}: {c['n']}/{q} (flood {c['flood']})", flush=True)

        for seg in ev_segs:
            if not want_more():
                break
            url, _ = resolve(seg["tar"])
            start, tries = seg["start"], 0
            while start is not None and want_more() and tries < 6:
                n, resume_at, err = stream_segment(seg, url, start, want_more, on_sample, args.max_gb_per_event * 1e9)
                with lock:
                    tot["bytes"] += n
                if err is not None:
                    tries += 1
                    print(f"   retry {tries} ({split}/{ev}) after {type(err).__name__}: {err}", flush=True)
                    time.sleep(2 ** tries)
                    # resume at the next REAL tar header after the last good sample (an arbitrary
                    # 512-aligned offset is usually inside file data -> "invalid header")
                    hit = probe(url, max(resume_at, seg["start"]))
                    start = hit[0] if hit else None
                else:
                    start = None
        with lock:
            fcsv.flush()
            print(f"[{split}] event {ev}: done {c['n']} (flood {c['flood']}); streamed {tot['bytes']/1e9:.1f} GB total",
                  flush=True)

    jobs = [(split, str(ev)) for split in args.splits for ev in splits[split]]
    with ThreadPoolExecutor(1 if args.dry_run else args.jobs) as ex:     # one HTTP stream per event
        for f in [ex.submit(fetch_event, s, e) for s, e in jobs]:
            f.result()
    fcsv.close()
    print(f"excluded near Trishuli: {tot['excluded']}; total streamed {tot['bytes']/1e9:.1f} GB")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("index")
    a.add_argument("--step", type=int, default=256 * 1024 * 1024)
    a.add_argument("--tol", type=int, default=8 * 1024 * 1024)
    a.add_argument("--workers", type=int, default=6)
    b = sub.add_parser("fetch")
    b.add_argument("--splits", nargs="+", default=["val", "test", "train"])
    b.add_argument("--val-per-event", type=int, default=700)
    b.add_argument("--test-per-event", type=int, default=1500)
    b.add_argument("--train-per-event", type=int, default=450)
    b.add_argument("--train-flood-share", type=float, default=0.5)
    b.add_argument("--max-gb-per-event", type=float, default=6.0)
    b.add_argument("--jobs", type=int, default=6, help="events downloaded in parallel (CDN limits per stream)")
    b.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    {"index": cmd_index, "fetch": cmd_fetch}[args.cmd](args)


if __name__ == "__main__":
    main()

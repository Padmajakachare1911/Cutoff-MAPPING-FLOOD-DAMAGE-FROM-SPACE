"""E6 cut-off robustness evaluation (synthetic correctness + frozen-run sensitivity)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np

from cutoff.contracts import ACCESS_STATUSES, SCENARIOS, VECTORS
from cutoff.geo.network import access_status, build_graph, closed_segments, edge_dropout, node_ways


def jaccard(left: set[str], right: set[str]) -> float:
    """Jaccard similarity, treating two empty sets as identical."""
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)


def scenario_table(run_dir: str | Path) -> list[dict]:
    """Read produced A/B/C layers and return the frozen E6 scenario comparison rows."""
    root = Path(run_dir)
    rows, cutoff_sets = [], {}
    for scenario in SCENARIOS:
        settlements = gpd.read_file(root / VECTORS[f"settlements_{scenario}"][0])
        roads = gpd.read_file(root / VECTORS[f"roads_{scenario}"][0])
        cutoff_sets[scenario] = set(settlements.loc[settlements.status == "cut_off", "sid"].astype(str))
        closed = roads.loc[roads.closed.astype(bool)]
        rows.append({"scenario": scenario, "closed_road_km": round(float(closed.length.sum()) / 1000, 3),
                     "closed_bridges": int(closed.loc[closed.bridge.astype(bool), "seg_id"].nunique()),
                     **{name: int((settlements.status == name).sum()) for name in ACCESS_STATUSES}})
    baseline = cutoff_sets["A"]
    for row in rows:
        row["cut_off_jaccard_vs_A"] = round(jaccard(baseline, cutoff_sets[row["scenario"]]), 3)
    return rows


def dropout_sensitivity(run_dir: str | Path, cfg: dict, fractions=(0.1, 0.2), runs: int = 20,
                        seed: int = 42) -> dict[str, dict]:
    """Measure per-settlement status flips under deterministic random OSM edge dropout."""
    root = Path(run_dir)
    roads = gpd.read_file(root / VECTORS["osm_roads"][0])
    hazard = gpd.read_file(root / VECTORS["hazard"][0])
    settlements = gpd.read_file(root / VECTORS["settlements"][0])
    targets = gpd.read_file(root / VECTORS["targets"][0])
    segments = node_ways(roads, float(cfg.get("access", {}).get("max_segment_m", 100)))
    graph = build_graph(segments, tuple(cfg.get("access", {}).get("vehicle_tiers", ("road", "track"))))
    rng = np.random.default_rng(seed)
    output = {}
    for scenario in SCENARIOS:
        closed = closed_segments(segments, hazard, scenario, cfg)
        reference = access_status(graph, settlements, targets, closed, cfg).set_index("sid").status
        scenario_result = {}
        for fraction in fractions:
            matches = {str(sid): 0 for sid in reference.index}
            for _ in range(runs):
                sampled = edge_dropout(graph, fraction, rng)
                status = access_status(sampled, settlements, targets, closed, cfg).set_index("sid").status
                for sid in reference.index:
                    matches[str(sid)] += int(status.loc[sid] == reference.loc[sid])
            per_settlement = {sid: {"stable_rate": count / runs, "flip_rate": 1 - count / runs}
                              for sid, count in matches.items()}
            stable_share = (sum(item["stable_rate"] >= 0.8 for item in per_settlement.values()) /
                            len(per_settlement) if per_settlement else 1.0)
            scenario_result[str(fraction)] = {"runs": runs, "stable_share_ge_80pct": stable_share,
                                              "settlements": per_settlement}
        output[scenario] = scenario_result
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    import yaml

    result = {"scenarios": scenario_table(args.run_dir),
              "dropout": dropout_sensitivity(args.run_dir, yaml.safe_load(args.config.read_text()))}
    text = json.dumps(result, indent=2)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()

"""Noded road graph, hazard-closure scenarios, and settlement access status."""
from __future__ import annotations

import math

import geopandas as gpd
import networkx as nx
import numpy as np
from shapely.geometry import MultiPoint, Point
from shapely.ops import split, substring

from cutoff.contracts import HAZARD_CLASSES, HIGH_CONFIDENCE_CLASSES, SCENARIOS
from cutoff.runctx import RunContext

STAGE = "access"
DEFAULT_SPEED_KMH = {
    "motorway": 60, "trunk": 50, "primary": 40, "secondary": 30, "tertiary": 25,
    "unclassified": 20, "residential": 15, "service": 10, "track": 10,
    "path": 4, "footway": 4, "steps": 3, "bridleway": 4,
}


def _bool(row, name: str) -> bool:
    value = row.get(name, False)
    return bool(value) and str(value).lower() not in {"no", "false", "0", "none"}


def _intersection_points(geom) -> list[Point]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type in {"LineString", "MultiLineString"}:
        lines = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
        return [Point(line.coords[0]) for line in lines] + [Point(line.coords[-1]) for line in lines]
    if hasattr(geom, "geoms"):
        return [point for part in geom.geoms for point in _intersection_points(part)]
    return []


def _same_grade(a, b) -> bool:
    return not (_bool(a, "bridge") or _bool(b, "bridge") or _bool(a, "tunnel") or _bool(b, "tunnel")) \
        and str(a.get("layer", "0")) == str(b.get("layer", "0"))


def node_ways(roads: gpd.GeoDataFrame, max_seg_m: float = 100.0) -> gpd.GeoDataFrame:
    """Split each way at same-grade crossings, then densify while preserving parent attributes."""
    if roads.crs is None or not roads.crs.is_projected:
        raise ValueError("roads must use a projected metre CRS")
    source = roads.reset_index(drop=True)
    if source.empty:
        out = source.copy()
        out["way_start"] = np.empty(0, dtype=object)
        out["way_end"] = np.empty(0, dtype=object)
        out["parent_idx"] = np.empty(0, dtype=int)
        out.insert(0, "seg_id", np.empty(0, dtype=int))
        return out
    output = []
    for i, row in source.iterrows():
        way = row.geometry
        points = []
        for j in source.sindex.query(way, predicate="intersects"):
            if i == j or not _same_grade(row, source.iloc[j]):
                continue
            points.extend(_intersection_points(way.intersection(source.iloc[j].geometry)))
        interior = [p for p in points if p.distance(Point(way.coords[0])) > 1e-7
                    and p.distance(Point(way.coords[-1])) > 1e-7]
        pieces = list(split(way, MultiPoint(interior)).geoms) if interior else [way]
        attrs = row.drop(labels=["geometry"]).to_dict()
        attrs["way_start"] = tuple(way.coords[0])
        attrs["way_end"] = tuple(way.coords[-1])
        attrs["parent_idx"] = i
        for piece in pieces:
            count = max(1, math.ceil(piece.length / max_seg_m))
            for k in range(count):
                geom = substring(piece, k * piece.length / count, (k + 1) * piece.length / count)
                output.append({**attrs, "geometry": geom})
    out = gpd.GeoDataFrame(output, geometry="geometry", crs=roads.crs)
    out.insert(0, "seg_id", np.arange(len(out), dtype=int))
    return out


def build_graph(segments: gpd.GeoDataFrame, tiers=("road", "track")) -> nx.MultiGraph:
    """Build an undirected keyed multigraph from segment endpoints rounded to one metre."""
    if segments.crs is None or not segments.crs.is_projected:
        raise ValueError("segments must use a projected metre CRS")
    graph = nx.MultiGraph()
    allowed = set(tiers)
    for _, row in segments.iterrows():
        if row.get("tier", "road") not in allowed:
            continue
        start = tuple(round(value) for value in row.geometry.coords[0])
        end = tuple(round(value) for value in row.geometry.coords[-1])
        if start == end:
            continue
        length = float(row.geometry.length)
        speed = DEFAULT_SPEED_KMH.get(str(row.get("highway", "unclassified")), 15) / 3.6
        seg_id = int(row.seg_id)
        graph.add_edge(start, end, key=seg_id, length=length, t=length / speed, bridge=_bool(row, "bridge"),
                       seg_id=seg_id)
    return graph


def _union_for(hazard: gpd.GeoDataFrame, classes) -> object | None:
    selected = hazard.loc[hazard["class"].isin([int(c) for c in classes])]
    return None if selected.empty else selected.geometry.union_all()


def closed_segments(segments: gpd.GeoDataFrame, hazard: gpd.GeoDataFrame, scenario: str,
                    cfg: dict | None = None) -> set[int]:
    """Return segment keys closed under scenario A, B, or bridge-approach-only C."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario}")
    access = (cfg or {}).get("access", cfg or {})
    all_hazard = _union_for(hazard, HAZARD_CLASSES)
    high = _union_for(hazard, HIGH_CONFIDENCE_CLASSES)
    if all_hazard is None:
        return set()
    closed: set[int] = set()
    bridge_groups = segments.loc[segments["bridge"].astype(bool)].groupby("parent_idx")
    bridge_classes = all_hazard if scenario == "A" else high
    approach_m = float(access.get("bridge_approach_m", 25))
    if bridge_classes is not None:
        for _, group in bridge_groups:
            first = group.iloc[0]
            approaches = MultiPoint([first.way_start, first.way_end]).buffer(approach_m)
            if approaches.intersects(bridge_classes):
                closed.update(group.seg_id.astype(int))
    nonbridge = segments.loc[~segments["bridge"].astype(bool)]
    if scenario == "A":
        distance = float(access.get("buffer_a_m", 15))
        closed.update(nonbridge.loc[nonbridge.geometry.distance(all_hazard) <= distance, "seg_id"].astype(int))
    elif scenario == "B" and high is not None:
        minimum = float(access.get("min_closed_length_b_m", 50))
        lengths = nonbridge.geometry.intersection(high).length
        closed.update(nonbridge.loc[lengths >= minimum, "seg_id"].astype(int))
    return closed


def _snap_points(graph: nx.MultiGraph, points: gpd.GeoDataFrame, max_m: float) -> dict:
    nodes = np.asarray(list(graph.nodes), dtype=float)
    result = {}
    for idx, point in points.geometry.items():
        if not len(nodes):
            result[idx] = None
            continue
        distances = np.hypot(nodes[:, 0] - point.x, nodes[:, 1] - point.y)
        nearest = int(distances.argmin())
        result[idx] = tuple(nodes[nearest]) if distances[nearest] <= max_m else None
    return result


def _without_closed(graph: nx.MultiGraph, closed: set[int]) -> nx.MultiGraph:
    result = graph.copy()
    result.remove_edges_from([(u, v, key) for u, v, key in result.edges(keys=True) if key in closed])
    return result


def access_status(graph: nx.MultiGraph, settlements: gpd.GeoDataFrame, targets: gpd.GeoDataFrame,
                  closed: set[int], cfg: dict | None = None) -> gpd.GeoDataFrame:
    """Classify settlements against baseline and post-closure multi-source travel times."""
    access = (cfg or {}).get("access", cfg or {})
    snap_max = float(access.get("snap_max_m", 500))
    degraded_ratio = float(access.get("degraded_ratio", 1.5))
    settlement_nodes = _snap_points(graph, settlements, snap_max)
    target_nodes = {node for node in _snap_points(graph, targets, snap_max).values() if node is not None}
    baseline = nx.multi_source_dijkstra_path_length(graph, target_nodes, weight="t") if target_nodes else {}
    after_graph = _without_closed(graph, closed)
    after = nx.multi_source_dijkstra_path_length(after_graph, target_nodes, weight="t") if target_nodes else {}
    out = settlements.copy()
    statuses, t0_values, t1_values = [], [], []
    for idx in out.index:
        node = settlement_nodes[idx]
        if node is None or node not in baseline:
            status, t0, t1 = "unknown", math.nan, math.nan
        else:
            t0 = baseline[node] / 60
            t1 = after.get(node, math.inf) / 60
            status = "cut_off" if math.isinf(t1) else \
                "degraded" if t1 > degraded_ratio * max(t0, 1e-9) else "connected"
        statuses.append(status)
        t0_values.append(t0)
        t1_values.append(t1)
    out["status"], out["t0_min"], out["t1_min"] = statuses, t0_values, t1_values
    return out


def edge_dropout(graph: nx.MultiGraph, frac: float, rng: np.random.Generator) -> nx.MultiGraph:
    """Remove a random fraction of keyed edges without mutating the source graph."""
    if not 0 <= frac <= 1:
        raise ValueError("dropout fraction must be between 0 and 1")
    result = graph.copy()
    edges = list(result.edges(keys=True))
    count = round(frac * len(edges))
    if count:
        selected = rng.choice(len(edges), size=count, replace=False)
        result.remove_edges_from([edges[int(i)] for i in selected])
    return result


def _settlement_refs(frame: gpd.GeoDataFrame, status: str) -> list[dict]:
    result = []
    for _, row in frame.to_crs(4326).loc[lambda data: data.status == status].iterrows():
        result.append({"sid": row.sid, "name": row["name"], "lon": row.geometry.x, "lat": row.geometry.y,
                       "t0_min": None if math.isnan(row.t0_min) else round(float(row.t0_min), 2)})
    return result


def stage_access(ctx: RunContext) -> dict:
    """Write scenario road/settlement layers and return schema-compatible summaries."""
    roads = gpd.read_file(ctx.path("osm_roads"))
    hazard = gpd.read_file(ctx.path("hazard"))
    settlements = gpd.read_file(ctx.path("settlements"))
    targets = gpd.read_file(ctx.path("targets"))
    max_segment = float(ctx.cfg.get("access", {}).get("max_segment_m", 100))
    segments = node_ways(roads, max_segment)
    vehicle = build_graph(segments, tuple(ctx.cfg.get("access", {}).get("vehicle_tiers", ("road", "track"))))
    all_tiers = build_graph(segments, ("road", "track", "trail"))
    results = []
    for scenario in ctx.cfg.get("access", {}).get("scenarios", ("A", "B", "C")):
        closed = closed_segments(segments, hazard, scenario, ctx.cfg)
        status = access_status(vehicle, settlements, targets, closed, ctx.cfg)
        with_trails = access_status(all_tiers, settlements, targets, closed, ctx.cfg)
        status["trail_access"] = (status.status == "cut_off") & with_trails.status.isin(("connected", "degraded"))
        road_status = segments.copy()
        road_status["closed"] = road_status.seg_id.isin(closed)
        status.to_file(ctx.path(f"settlements_{scenario}"), driver="GPKG")
        road_status[["seg_id", "closed", "bridge", "geometry"]].to_file(
            ctx.path(f"roads_{scenario}"), driver="GPKG")
        closed_rows = road_status.loc[road_status.closed]
        counts = {name: int((status.status == name).sum())
                  for name in ("connected", "degraded", "cut_off", "unknown")}
        results.append({"scenario": scenario, "description": SCENARIOS[scenario],
                        "closed_road_km": round(float(closed_rows.length.sum()) / 1000, 2),
                        "closed_bridges": int(closed_rows.loc[closed_rows.bridge].parent_idx.nunique()),
                        "counts": counts, "cut_off": _settlement_refs(status, "cut_off"),
                        "degraded": _settlement_refs(status, "degraded")})
    ctx.log(STAGE, event="complete", scenarios=results)
    return {"access": results}


__all__ = ["access_status", "build_graph", "closed_segments", "edge_dropout", "node_ways", "stage_access"]

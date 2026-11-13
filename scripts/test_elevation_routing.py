"""
Quick verification that elevation_weight actually influences route selection.

Loads the GraphML directly and recomputes grades in memory, without invoking
the application loader or modifying either graph cache.

Usage:
    uv run python scripts/test_elevation_routing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import networkx as nx
import osmnx as ox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.graph.elevation import MAX_GRADE, compute_edge_grades  # noqa: E402
from src.routing.cost import (  # noqa: E402
    CONSECUTIVE_CLIMB_RATIO_THRESHOLD,
    ELEVATION_SENSITIVITY,
    MODERATE_DOWNHILL_GRADE_THRESHOLD,
    MODERATE_DOWNHILL_MULTIPLIER,
    STEEP_DOWNHILL_GRADE_THRESHOLD,
    STEEP_DOWNHILL_MULTIPLIER,
    downhill_cost_multiplier,
    edge_cost,
    elevation_cost_ratio,
)
from src.routing.pathfinder import compute_route_metrics, find_route, nearest_node  # noqa: E402

GRAPH_CACHE_PATH = PROJECT_ROOT / "data" / "montevideo.graphml"

# Plaza Independencia -> Tres Cruces
ORIGIN = (-34.9064755, -56.1997577)
DEST = (-34.892518, -56.1671127)

WEIGHTS = [0.0, 1.0, 2.0, 5.0, 10.0]


def main() -> int:
    print("=" * 70)
    print("1. Edge cost formula sanity check (linear grade penalty)")
    print("=" * 70)
    for grade in (0.03, 0.05, 0.08, 0.15, 0.25, 0.45):
        costs = [edge_cost(100.0, grade, w) for w in WEIGHTS]
        print(f"  grade={grade:.2f}  " + "  ".join(f"w={w:>4.1f}->{c:6.2f}" for w, c in zip(WEIGHTS, costs)))
    downhill_cost = edge_cost(100.0, -0.10, 10.0)
    print(f"  downhill grade=-0.10, w=10.0 -> {downhill_cost:.2f} (expected 75.00)")
    assert downhill_cost == 75.0, "A 10% downhill edge must cost 75% of its length"
    assert downhill_cost_multiplier(-(MODERATE_DOWNHILL_GRADE_THRESHOLD - 0.0001)) == 1.0
    assert downhill_cost_multiplier(-MODERATE_DOWNHILL_GRADE_THRESHOLD) == MODERATE_DOWNHILL_MULTIPLIER
    assert downhill_cost_multiplier(-STEEP_DOWNHILL_GRADE_THRESHOLD) == MODERATE_DOWNHILL_MULTIPLIER
    assert downhill_cost_multiplier(-(STEEP_DOWNHILL_GRADE_THRESHOLD + 0.0001)) == STEEP_DOWNHILL_MULTIPLIER
    assert edge_cost(100.0, -MODERATE_DOWNHILL_GRADE_THRESHOLD, 10.0) == 75.0
    assert edge_cost(100.0, -(STEEP_DOWNHILL_GRADE_THRESHOLD + 0.05), 10.0) == 50.0
    expected_linear_cost = 100.0 * (1 + 5.0 * 0.05 * ELEVATION_SENSITIVITY)
    assert edge_cost(100.0, 0.05, 5.0) == expected_linear_cost, (
        "Uphill cost must use the configured linear sensitivity"
    )
    ratio_at_threshold = elevation_cost_ratio(0.05, 10.0)
    assert abs(ratio_at_threshold - CONSECUTIVE_CLIMB_RATIO_THRESHOLD) < 1e-12
    assert not ratio_at_threshold > CONSECUTIVE_CLIMB_RATIO_THRESHOLD
    assert (
        elevation_cost_ratio(0.0501, 10.0)
        > CONSECUTIVE_CLIMB_RATIO_THRESHOLD
    )
    against_traffic_cost = edge_cost(
        100.0,
        0.0,
        0.0,
        is_against_traffic=True,
        max_against_traffic_blocks=1,
    )
    assert against_traffic_cost == 180.0, "Allowed against-traffic edges must cost 1.8x"

    consecutive_test_graph = nx.DiGraph()
    consecutive_test_graph.add_edge(1, 2, length=100.0, grade=0.0501)
    consecutive_test_graph.add_edge(2, 4, length=100.0, grade=0.0501)
    consecutive_test_graph.add_edge(1, 3, length=180.0, grade=0.0)
    consecutive_test_graph.add_edge(3, 4, length=180.0, grade=0.0)
    consecutive_route = find_route(
        consecutive_test_graph,
        1,
        4,
        elevation_weight=10.0,
    )
    assert consecutive_route == [1, 3, 4], (
        "The second consecutive costly uphill edge must receive the 10% surcharge"
    )

    print()
    print("=" * 70)
    print("2. Graph grade attribute check (data/montevideo.graphml)")
    print("=" * 70)
    G_multi = ox.load_graphml(GRAPH_CACHE_PATH)
    compute_edge_grades(G_multi)
    grades = np.array([d.get("grade", 0.0) for _, _, d in G_multi.edges(data=True)], dtype=float)
    print(f"  edges: {len(grades)}")
    print(f"  grade min={grades.min():.4f} max={grades.max():.4f} mean={grades.mean():.5f}")
    print(f"  edges with grade == 0.0 exactly: {(grades == 0.0).mean() * 100:.1f}%")
    print(f"  edges with |grade| > 0.01: {(np.abs(grades) > 0.01).mean() * 100:.1f}%")
    print(f"  edges with |grade| > 0.03: {(np.abs(grades) > 0.03).mean() * 100:.1f}%")
    assert grades.min() >= -MAX_GRADE and grades.max() <= MAX_GRADE, (
        f"Grade must be clamped to +/-{MAX_GRADE:.0%}"
    )
    assert not np.all(grades == 0.0), "All grades are zero — elevation enrichment did not run!"

    print()
    print("=" * 70)
    print(f"3. Route comparison: Plaza Independencia {ORIGIN} -> Tres Cruces {DEST}")
    print("=" * 70)
    G = ox.convert.to_digraph(G_multi)
    origin_node = nearest_node(G, *ORIGIN)
    dest_node = nearest_node(G, *DEST)

    results = []
    for w in WEIGHTS:
        path = find_route(G, origin_node, dest_node, elevation_weight=w)
        m = compute_route_metrics(G, path, elevation_weight=w)
        results.append((w, m))
        print(
            f"  elevation_weight={w:5.1f}  nodes={m.node_count:3d}  "
            f"distance={m.total_distance_m:8.1f}m  elevation_gain={m.total_elevation_gain_m:6.2f}m"
        )

    gains = [m.total_elevation_gain_m for _, m in results]
    distances = [m.total_distance_m for _, m in results]
    if max(gains) - min(gains) > 0.5 or max(distances) - min(distances) > 0.5:
        print("\n  -> elevation_weight measurably changes the route for this origin/destination.")
    else:
        print(
            "\n  -> Route is identical across all weights for this specific origin/destination pair. "
            "This does NOT necessarily mean elevation_weight is broken (see edge_cost sanity check "
            "above, which confirms the formula itself scales correctly) — it means the road network "
            "does not offer a lower-elevation-gain alternative between these two points worth the "
            "distance trade-off. Try a pair with more elevation contrast (e.g. Rambla <-> a node near "
            "92m elevation) to see the effect."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

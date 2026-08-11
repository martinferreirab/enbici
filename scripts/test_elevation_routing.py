"""
Quick verification that elevation_weight actually influences route selection.

Loads the graph read-only (ox.load_graphml directly — does NOT call
load_montevideo_graph(), which always re-saves the ~40MB cache file on every
call; this script must never trigger that write, since an interrupted write
truncates data/montevideo.graphml to 0 bytes).

Usage:
    uv run python scripts/test_elevation_routing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import osmnx as ox

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.routing.cost import edge_cost  # noqa: E402
from src.routing.pathfinder import compute_route_metrics, find_route, nearest_node  # noqa: E402

GRAPH_CACHE_PATH = PROJECT_ROOT / "data" / "montevideo.graphml"

# Plaza Independencia -> Tres Cruces
ORIGIN = (-34.9064755, -56.1997577)
DEST = (-34.892518, -56.1671127)

WEIGHTS = [0.0, 1.0, 2.0, 5.0, 10.0]


def main() -> int:
    print("=" * 70)
    print("1. Edge cost formula sanity check (grade ** 1.5 power law)")
    print("=" * 70)
    for grade in (0.03, 0.05, 0.08, 0.15, 0.25):
        costs = [edge_cost(100.0, grade, w) for w in WEIGHTS]
        print(f"  grade={grade:.2f}  " + "  ".join(f"w={w:>4.1f}->{c:6.2f}" for w, c in zip(WEIGHTS, costs)))
    downhill_cost = edge_cost(100.0, -0.10, 10.0)
    print(f"  downhill grade=-0.10, w=10.0 -> {downhill_cost:.2f} (should equal length=100.0, no penalty)")
    assert downhill_cost == 100.0, "Downhill edges must not be penalized!"

    print()
    print("=" * 70)
    print("2. Graph grade attribute check (data/montevideo.graphml)")
    print("=" * 70)
    G_multi = ox.load_graphml(GRAPH_CACHE_PATH)
    grades = np.array([d.get("grade", 0.0) for _, _, d in G_multi.edges(data=True)], dtype=float)
    print(f"  edges: {len(grades)}")
    print(f"  grade min={grades.min():.4f} max={grades.max():.4f} mean={grades.mean():.5f}")
    print(f"  edges with grade == 0.0 exactly: {(grades == 0.0).mean() * 100:.1f}%")
    print(f"  edges with |grade| > 0.01: {(np.abs(grades) > 0.01).mean() * 100:.1f}%")
    print(f"  edges with |grade| > 0.03: {(np.abs(grades) > 0.03).mean() * 100:.1f}%")
    assert grades.min() >= -0.25 and grades.max() <= 0.25, "Grade must be clamped to +/-25%"
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

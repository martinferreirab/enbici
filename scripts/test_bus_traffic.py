"""Offline checks for live bus parsing, edge matching, and routing penalties."""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import networkx as nx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.api import buses as buses_api  # noqa: E402
from src.api.buses import (  # noqa: E402
    BusPosition,
    _parse_fresh_bus_positions,
    map_bus_positions_to_edges,
)
from src.routing.cost import bus_traffic_multiplier, edge_cost  # noqa: E402
from src.routing.pathfinder import compute_route_metrics, find_route  # noqa: E402


def main() -> int:
    with (
        patch.dict(
            "os.environ",
            {
                "MONTEVIDEO_CLIENT_ID": "test-client",
                "MONTEVIDEO_CLIENT_SECRET": "test-secret",
            },
        ),
        patch.object(buses_api.requests, "post") as post,
    ):
        response = Mock()
        response.json.return_value = {
            "access_token": "test-token",
            "expires_in": 3600,
        }
        post.return_value = response
        buses_api._token = None
        buses_api._token_expires_at = 0.0

        assert buses_api._get_access_token() == "test-token"
        request = post.call_args.kwargs
        assert post.call_args.args[0] == (
            "https://mvdapi-auth.montevideo.gub.uy"
            "/auth/realms/pci/protocol/openid-connect/token"
        )
        assert request["data"] == {
            "grant_type": "client_credentials",
            "client_id": "test-client",
            "client_secret": "test-secret",
        }
        assert request["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
        assert "auth" not in request

    assert bus_traffic_multiplier(0) == 1.0
    assert bus_traffic_multiplier(1) == 1.15
    assert bus_traffic_multiplier(2) == 1.15
    assert bus_traffic_multiplier(3) == 1.30
    assert edge_cost(100.0, 0.0, 0.0, bus_count=0) == 100.0
    assert math.isclose(edge_cost(100.0, 0.0, 0.0, bus_count=1), 115.0)
    assert math.isclose(edge_cost(100.0, 0.0, 0.0, bus_count=3), 130.0)

    now = datetime.now(timezone.utc)
    parsed_positions = _parse_fresh_bus_positions(
        [
            {
                "eType": "buses",
                "company": "CUTCSA",
                "timestamp": now.isoformat(),
                "location": {"type": "Point", "coordinates": [-56.2, -34.9]},
            },
            {
                "vehicleType": "bus",
                "timestamp": (now - timedelta(minutes=6)).isoformat(),
                "location": {"type": "Point", "coordinates": [-56.2, -34.9]},
            },
            {
                "eType": "taxi",
                "timestamp": now.isoformat(),
                "location": {"type": "Point", "coordinates": [-56.2, -34.9]},
            },
        ]
    )
    assert len(parsed_positions) == 1, "Only fresh bus positions should be used"

    graph = nx.DiGraph()
    graph.graph["crs"] = "EPSG:4326"
    graph.add_node(1, x=-56.2000, y=-34.9000)
    graph.add_node(2, x=-56.1990, y=-34.9000)
    graph.add_node(3, x=-56.1980, y=-34.9000)
    graph.add_node(4, x=-56.2000, y=-34.9020)
    graph.add_node(5, x=-56.1980, y=-34.9020)
    graph.add_edge(1, 2, length=90.0, grade=0.0)
    graph.add_edge(2, 3, length=90.0, grade=0.0)
    graph.add_edge(1, 4, length=68.0, grade=0.0)
    graph.add_edge(4, 5, length=68.0, grade=0.0)
    graph.add_edge(5, 3, length=68.0, grade=0.0)

    positions = [
        BusPosition(longitude=-56.1995, latitude=-34.9000),
        BusPosition(longitude=-56.1995, latitude=-34.9000),
        BusPosition(longitude=-56.1995, latitude=-34.9000),
    ]
    edge_counts, matched = map_bus_positions_to_edges(graph, positions)
    assert matched == 3
    assert edge_counts.get((1, 2), 0) + edge_counts.get((2, 3), 0) == 3

    route = find_route(
        graph,
        1,
        3,
        elevation_weight=0.0,
        bus_counts=edge_counts,
    )
    assert route != [1, 2, 3], "The route should avoid the bus-heavy shortcut"
    metrics = compute_route_metrics(
        graph,
        route,
        elevation_weight=0.0,
        bus_counts=edge_counts,
    )
    assert metrics.live_buses_near_route == 0

    print("Live bus cost, matching, and route selection checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

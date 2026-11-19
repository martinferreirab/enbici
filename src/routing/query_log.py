"""Registro de cada consulta de ruta (Streamlit y API) en un CSV, con los datos de penalización por ómnibus."""

from __future__ import annotations

import csv
import logging
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.config import QUERY_LOG_PATH
from src.routing.cost import bus_traffic_multiplier

if TYPE_CHECKING:
    from networkx import DiGraph

    from src.api.buses import BusTraffic
    from src.routing.pathfinder import RouteMetrics

logger = logging.getLogger(__name__)

FIELDS = [
    "timestamp", "source",
    "origin_place", "origin_lat", "origin_lon",
    "dest_place", "dest_lat", "dest_lon",
    "elevation_weight", "wind_weight", "bus_weight",
    "allow_parks", "max_against_traffic_blocks",
    "distance_km", "elevation_gain_m", "node_count",
    "bus_data_available", "bus_data_fetched_at",
    "buses_fresh_city", "buses_matched_city",
    "live_buses_near_route", "route_edges_with_bus", "route_meters_with_bus",
    "mult_bus_1_2", "mult_bus_3_mas", "bus_penalty_extra_m",
]

_lock = threading.Lock()


def log_route_query(
    G: DiGraph,
    path: list,
    metrics: RouteMetrics,
    *,
    source: str,
    origin: tuple[float, float],
    dest: tuple[float, float],
    origin_place: str | None,
    dest_place: str | None,
    wind_weight: float,
    bus_weight: float,
    allow_parks: bool,
    max_against_traffic_blocks: int,
    bus_traffic: BusTraffic | None,
) -> None:
    """Agrega una fila a ``data/consultas_rutas.csv``. Nunca interrumpe el ruteo si falla."""
    try:
        counts = bus_traffic.edge_counts if bus_traffic else {}
        edges_with_bus = 0
        meters_with_bus = 0.0
        extra_m = 0.0  # metros "equivalentes" que suma la penalización por ómnibus
        for u, v in zip(path[:-1], path[1:]):
            n = counts.get((u, v), 0)
            if n:
                length = G.edges[u, v].get("length", 0.0)
                edges_with_bus += 1
                meters_with_bus += length
                extra_m += length * (bus_traffic_multiplier(n, bus_weight) - 1.0)

        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": source,
            "origin_place": origin_place or "",
            "origin_lat": round(origin[0], 6),
            "origin_lon": round(origin[1], 6),
            "dest_place": dest_place or "",
            "dest_lat": round(dest[0], 6),
            "dest_lon": round(dest[1], 6),
            "elevation_weight": metrics.elevation_weight,
            "wind_weight": wind_weight,
            "bus_weight": bus_weight,
            "allow_parks": allow_parks,
            "max_against_traffic_blocks": max_against_traffic_blocks,
            "distance_km": round(metrics.total_distance_m / 1000, 3),
            "elevation_gain_m": round(metrics.total_elevation_gain_m, 1),
            "node_count": metrics.node_count,
            "bus_data_available": bus_traffic is not None,
            "bus_data_fetched_at": bus_traffic.fetched_at.isoformat(timespec="seconds") if bus_traffic else "",
            "buses_fresh_city": bus_traffic.fresh_positions if bus_traffic else "",
            "buses_matched_city": bus_traffic.matched_positions if bus_traffic else "",
            "live_buses_near_route": metrics.live_buses_near_route if metrics.live_buses_near_route is not None else "",
            "route_edges_with_bus": edges_with_bus,
            "route_meters_with_bus": round(meters_with_bus, 1),
            "mult_bus_1_2": round(bus_traffic_multiplier(1, bus_weight), 2),
            "mult_bus_3_mas": round(bus_traffic_multiplier(3, bus_weight), 2),
            "bus_penalty_extra_m": round(extra_m, 1),
        }

        with _lock:
            QUERY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            is_new = not QUERY_LOG_PATH.exists()
            with QUERY_LOG_PATH.open("a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                if is_new:
                    writer.writeheader()
                writer.writerow(row)
    except Exception:  # el log es auxiliar: nunca debe romper una consulta de ruta
        logger.exception("No se pudo registrar la consulta de ruta en %s", QUERY_LOG_PATH)

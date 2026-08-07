"""Búsqueda de rutas y métricas del recorrido."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx
import osmnx as ox

from src.routing.cost import edge_cost, _calculate_bearing

if TYPE_CHECKING:
    from networkx import DiGraph
    from src.api.weather import WindData


@dataclass(frozen=True)
class RouteMetrics:
    """Métricas agregadas de una ruta calculada."""

    elevation_weight: float
    total_distance_m: float
    total_elevation_gain_m: float
    node_count: int
    wind_weight: float = 0.0
    average_wind_speed_ms: float = 0.0
    average_headwind_factor: float = 0.0


def nearest_node(G: DiGraph, lat: float, lon: float) -> int:
    """Devuelve el nodo del grafo más cercano a un par lat/lon."""
    return ox.distance.nearest_nodes(G, lon, lat)


def find_route(
    G: DiGraph,
    origin_node: int,
    dest_node: int,
    elevation_weight: float,
    wind_data: WindData | None = None,
    wind_weight: float = 0.0,
    allow_parks: bool = True,
) -> list[int]:
    """Calcula la ruta de costo mínimo entre dos nodos (Dijkstra)."""

    def weight_func(u: int, v: int, data: dict) -> float:
        edge_bearing = None
        if wind_data and wind_weight > 0:
            # Calculate bearing from node coordinates
            lat1 = G.nodes[u].get("y", 0.0)
            lon1 = G.nodes[u].get("x", 0.0)
            lat2 = G.nodes[v].get("y", 0.0)
            lon2 = G.nodes[v].get("x", 0.0)
            edge_bearing = _calculate_bearing(lat1, lon1, lat2, lon2)

        return edge_cost(
            data.get("length", 0.0),
            data.get("grade", 0.0),
            elevation_weight,
            wind_data=wind_data,
            wind_weight=wind_weight,
            edge_bearing_deg=edge_bearing,
            is_park_path=data.get("is_park_path", False),
            allow_parks=allow_parks,
        )

    return nx.shortest_path(G, origin_node, dest_node, weight=weight_func)


def compute_route_metrics(
    G: DiGraph,
    path: list[int],
    elevation_weight: float,
    wind_data: WindData | None = None,
    wind_weight: float = 0.0,
    allow_parks: bool = True,
) -> RouteMetrics:
    """Calcula distancia total, desnivel y métricas de viento de una ruta."""
    total_distance = 0.0
    total_gain = 0.0
    wind_speed_sum = 0.0
    headwind_factor_sum = 0.0
    edge_count = 0

    for u, v in zip(path[:-1], path[1:], strict=True):
        edge_data = G.edges[u, v]
        length = edge_data.get("length", 0.0)
        total_distance += length

        elev_u = G.nodes[u].get("elevation", 0.0)
        elev_v = G.nodes[v].get("elevation", 0.0)
        total_gain += max(0.0, elev_v - elev_u)

        # Calculate wind metrics
        if wind_data and wind_weight > 0:
            lat1 = G.nodes[u].get("y", 0.0)
            lon1 = G.nodes[u].get("x", 0.0)
            lat2 = G.nodes[v].get("y", 0.0)
            lon2 = G.nodes[v].get("x", 0.0)
            edge_bearing = _calculate_bearing(lat1, lon1, lat2, lon2)

            wind_dir = wind_data.direction_degrees % 360
            angle_diff = (wind_dir - edge_bearing) % 360
            if angle_diff > 180:
                angle_diff = angle_diff - 360

            cos_angle = math.cos(math.radians(angle_diff))
            headwind_factor = (1.0 + cos_angle) / 2.0

            wind_speed_sum += wind_data.speed_ms
            headwind_factor_sum += headwind_factor
            edge_count += 1

    average_wind_speed = (
        wind_speed_sum / edge_count if edge_count > 0 else 0.0
    )
    average_headwind_factor = (
        headwind_factor_sum / edge_count if edge_count > 0 else 0.0
    )

    return RouteMetrics(
        elevation_weight=elevation_weight,
        total_distance_m=total_distance,
        total_elevation_gain_m=total_gain,
        node_count=len(path),
        wind_weight=wind_weight,
        average_wind_speed_ms=average_wind_speed,
        average_headwind_factor=average_headwind_factor,
    )

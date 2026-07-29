"""Búsqueda de rutas y métricas del recorrido."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx
import osmnx as ox

from src.routing.cost import edge_cost

if TYPE_CHECKING:
    from networkx import DiGraph


@dataclass(frozen=True)
class RouteMetrics:
    """Métricas agregadas de una ruta calculada."""

    elevation_weight: float
    total_distance_m: float
    total_elevation_gain_m: float
    node_count: int


def nearest_node(G: DiGraph, lat: float, lon: float) -> int:
    """Devuelve el nodo del grafo más cercano a un par lat/lon."""
    return ox.distance.nearest_nodes(G, lon, lat)


def find_route(
    G: DiGraph,
    origin_node: int,
    dest_node: int,
    elevation_weight: float,
) -> list[int]:
    """Calcula la ruta de costo mínimo entre dos nodos (Dijkstra)."""

    def weight_func(u: int, v: int, data: dict) -> float:
        return edge_cost(
            data.get("length", 0.0),
            data.get("grade", 0.0),
            elevation_weight,
        )

    return nx.shortest_path(G, origin_node, dest_node, weight=weight_func)


def compute_route_metrics(
    G: DiGraph,
    path: list[int],
    elevation_weight: float,
) -> RouteMetrics:
    """Calcula distancia total y desnivel positivo acumulado de una ruta."""
    total_distance = 0.0
    total_gain = 0.0

    for u, v in zip(path[:-1], path[1:], strict=True):
        edge_data = G.edges[u, v]
        length = edge_data.get("length", 0.0)
        total_distance += length

        elev_u = G.nodes[u].get("elevation", 0.0)
        elev_v = G.nodes[v].get("elevation", 0.0)
        total_gain += max(0.0, elev_v - elev_u)

    return RouteMetrics(
        elevation_weight=elevation_weight,
        total_distance_m=total_distance,
        total_elevation_gain_m=total_gain,
        node_count=len(path),
    )

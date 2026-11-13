"""Búsqueda de rutas y métricas del recorrido."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import networkx as nx
import osmnx as ox

from src.routing.cost import (
    CONSECUTIVE_CLIMB_MULTIPLIER,
    CONSECUTIVE_CLIMB_RATIO_THRESHOLD,
    _calculate_bearing,
    edge_cost,
    elevation_cost_ratio,
)

if TYPE_CHECKING:
    from networkx import DiGraph
    from src.api.weather import WindData, WindGrid


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
    live_buses_near_route: int | None = None


def nearest_node(G: DiGraph, lat: float, lon: float) -> int:
    """Devuelve el nodo del grafo más cercano a un par lat/lon."""
    return ox.distance.nearest_nodes(G, lon, lat)


def find_route(
    G: DiGraph,
    origin_node: int,
    dest_node: int,
    elevation_weight: float,
    wind_data: WindData | WindGrid | None = None,
    wind_weight: float = 0.0,
    allow_parks: bool = True,
    max_against_traffic_blocks: int = 0,
    bus_counts: Mapping[tuple[int, int], int] | None = None,
) -> list[int]:
    """Calcula la ruta de costo mínimo, considerando subidas y buses cercanos."""

    def edge_weight(u: int, v: int, data: dict) -> float:
        edge_bearing = None
        wind_for_edge = wind_data

        if wind_data and wind_weight > 0:
            # Calculate bearing from node coordinates
            lat1 = G.nodes[u].get("y", 0.0)
            lon1 = G.nodes[u].get("x", 0.0)
            lat2 = G.nodes[v].get("y", 0.0)
            lon2 = G.nodes[v].get("x", 0.0)
            edge_bearing = _calculate_bearing(lat1, lon1, lat2, lon2)

            # If wind_data is a WindGrid, get wind for this edge's location
            from src.api.weather import WindGrid
            if isinstance(wind_data, WindGrid):
                wind_for_edge = wind_data.get_wind_at_location(lat1, lon1)

        grade = data.get("grade", 0.0)
        cost = edge_cost(
            data.get("length", 0.0),
            grade,
            elevation_weight,
            wind_data=wind_for_edge,
            wind_weight=wind_weight,
            edge_bearing_deg=edge_bearing,
            is_park_path=data.get("is_park_path", False),
            allow_parks=allow_parks,
            is_against_traffic=data.get("is_against_traffic", False),
            max_against_traffic_blocks=max_against_traffic_blocks,
            bus_count=bus_counts.get((u, v), 0) if bus_counts else 0,
        )
        return cost

    state_graph = nx.DiGraph()
    target = object()

    for u, v, data in G.edges(data=True):
        grade = data.get("grade", 0.0)
        is_costly_uphill = (
            elevation_cost_ratio(grade, elevation_weight)
            > CONSECUTIVE_CLIMB_RATIO_THRESHOLD
        )
        base_edge_cost = edge_weight(u, v, data)
        for previous_edge_was_costly_uphill in (False, True):
            source_state = (u, previous_edge_was_costly_uphill)
            destination_state = (v, is_costly_uphill)
            weight = base_edge_cost
            if previous_edge_was_costly_uphill and is_costly_uphill:
                weight *= CONSECUTIVE_CLIMB_MULTIPLIER
            state_graph.add_edge(
                source_state,
                destination_state,
                weight=weight,
            )

    state_graph.add_edge((dest_node, False), target, weight=0.0)
    state_graph.add_edge((dest_node, True), target, weight=0.0)
    state_path = nx.shortest_path(
        state_graph,
        (origin_node, False),
        target,
        weight="weight",
    )
    return [node for node, _ in state_path[:-1]]


def compute_route_metrics(
    G: DiGraph,
    path: list[int],
    elevation_weight: float,
    wind_data: WindData | WindGrid | None = None,
    wind_weight: float = 0.0,
    allow_parks: bool = True,
    max_against_traffic_blocks: int = 0,
    bus_counts: Mapping[tuple[int, int], int] | None = None,
) -> RouteMetrics:
    """Calcula distancia total, desnivel y métricas de viento de una ruta."""
    total_distance = 0.0
    total_gain = 0.0
    wind_speed_sum = 0.0
    headwind_factor_sum = 0.0
    edge_count = 0
    live_buses_near_route = 0

    for u, v in zip(path[:-1], path[1:], strict=True):
        edge_data = G.edges[u, v]
        if bus_counts:
            live_buses_near_route += bus_counts.get((u, v), 0)
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

            # Handle both WindData and WindGrid
            from src.api.weather import WindGrid
            if isinstance(wind_data, WindGrid):
                edge_wind = wind_data.get_wind_at_location(lat1, lon1)
                if not edge_wind:
                    continue
            else:
                edge_wind = wind_data

            wind_dir = edge_wind.direction_degrees % 360
            angle_diff = (wind_dir - edge_bearing) % 360
            if angle_diff > 180:
                angle_diff = angle_diff - 360

            cos_angle = math.cos(math.radians(angle_diff))
            headwind_factor = (1.0 + cos_angle) / 2.0

            wind_speed_sum += edge_wind.speed_ms
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
        live_buses_near_route=(
            live_buses_near_route if bus_counts is not None else None
        ),
    )

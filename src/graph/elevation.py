"""Elevación de nodos y cálculo de pendiente (grade) por arista."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import networkx as nx
import requests
from geopy.distance import geodesic

if TYPE_CHECKING:
    from networkx import DiGraph

logger = logging.getLogger(__name__)

OPEN_ELEVATION_URL = "https://api.open-elevation.com/api/v1/lookup"
MAX_GRADE = 0.25
BATCH_SIZE = 100

# Referencia topográfica para mock (Cerro de Montevideo)
_CERRO_REF = (-34.879, -56.213)


def _mock_elevation(lat: float, lon: float) -> float:
    """Estima elevación cuando la API externa no está disponible."""
    dist_m = geodesic((lat, lon), _CERRO_REF).meters
    base = 15.0
    cerro_boost = max(0.0, 130.0 - dist_m * 0.08)
    coastal = max(0.0, (lon + 56.25) * 8.0)
    return base + cerro_boost * 0.3 + coastal * 0.1


def _fetch_elevations_batch(lats: list[float], lons: list[float]) -> list[float]:
    """Consulta elevaciones en Open-Elevation para un lote de coordenadas."""
    locations = [{"latitude": lat, "longitude": lon} for lat, lon in zip(lats, lons, strict=True)]
    response = requests.post(
        OPEN_ELEVATION_URL,
        json={"locations": locations},
        timeout=60,
    )
    response.raise_for_status()
    results = response.json()["results"]
    return [float(r["elevation"]) for r in results]


def add_node_elevations(G: nx.MultiDiGraph, use_api: bool = True) -> None:
    """Asigna el atributo ``elevation`` a cada nodo del grafo."""
    nodes = list(G.nodes(data=True))
    lats = [data["y"] for _, data in nodes]
    lons = [data["x"] for _, data in nodes]

    elevations: list[float] = []
    api_available = use_api

    if api_available:
        try:
            for start in range(0, len(lats), BATCH_SIZE):
                batch_lats = lats[start : start + BATCH_SIZE]
                batch_lons = lons[start : start + BATCH_SIZE]
                elevations.extend(_fetch_elevations_batch(batch_lats, batch_lons))
                logger.info(
                    "Elevaciones API: %d / %d nodos",
                    min(start + BATCH_SIZE, len(lats)),
                    len(lats),
                )
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.warning("Fallo API de elevación (%s). Usando mock.", exc)
            api_available = False
            elevations = []

    if not api_available or len(elevations) != len(nodes):
        elevations = [_mock_elevation(lat, lon) for lat, lon in zip(lats, lons, strict=True)]

    for (node_id, _), elev in zip(nodes, elevations, strict=True):
        G.nodes[node_id]["elevation"] = elev


def compute_edge_grades(G: nx.MultiDiGraph) -> None:
    """Calcula y persiste ``grade`` (pendiente relativa) en cada arista."""
    for u, v, _key, data in G.edges(keys=True, data=True):
        length = data.get("length", 0.0)
        if length <= 0:
            data["grade"] = 0.0
            continue

        elev_u = G.nodes[u].get("elevation", 0.0)
        elev_v = G.nodes[v].get("elevation", 0.0)
        grade = (elev_v - elev_u) / length
        data["grade"] = max(-MAX_GRADE, min(MAX_GRADE, grade))


def enrich_graph_with_elevation(G: nx.MultiDiGraph) -> None:
    """Agrega elevaciones y pendientes si aún no están presentes en el grafo."""
    sample_node = next(iter(G.nodes(data=True)))[1]
    if "elevation" not in sample_node:
        add_node_elevations(G)
    if not any("grade" in data for _, _, data in G.edges(data=True)):
        compute_edge_grades(G)


def graph_has_elevation(G: nx.MultiDiGraph) -> bool:
    """Indica si el grafo ya tiene elevaciones y pendientes calculadas."""
    if not G.nodes:
        return False
    sample_node = next(iter(G.nodes(data=True)))[1]
    has_elevation = "elevation" in sample_node
    has_grade = any("grade" in data for _, _, data in G.edges(data=True))
    return has_elevation and has_grade

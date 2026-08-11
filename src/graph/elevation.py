"""Elevación de nodos y cálculo de pendiente (grade) por arista."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import networkx as nx
import requests

if TYPE_CHECKING:
    from networkx import DiGraph

logger = logging.getLogger(__name__)

OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
MAX_GRADE = 0.25
BATCH_SIZE = 1000


def _fetch_elevations_batch(lats: list[float], lons: list[float]) -> list[float] | None:
    """Fetch elevations from Open-Meteo Elevation API using POST (no URL length limits)."""
    max_retries = 5
    retry_delay = 10.0

    for attempt in range(max_retries):
        try:
            payload = {
                "latitude": lats,
                "longitude": lons,
            }
            response = requests.post(
                OPEN_METEO_ELEVATION_URL,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            return [float(elev) for elev in data.get("elevation", [])]
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                logger.warning("Rate limited. Retrying in %.1fs (attempt %d/%d)...", retry_delay, attempt + 1, max_retries)
                time.sleep(retry_delay)
                retry_delay *= 1.5
            else:
                logger.warning("Open-Meteo elevation API error: %s", exc)
                return None
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.warning("Open-Meteo elevation API error: %s", exc)
            return None

    return None


def add_node_elevations(G: nx.MultiDiGraph) -> None:
    """Fetch real elevations from Open-Meteo for all nodes in the graph."""
    nodes = list(G.nodes(data=True))
    lats = [data["y"] for _, data in nodes]
    lons = [data["x"] for _, data in nodes]

    elevations: list[float] = []
    total_nodes = len(lats)

    logger.info("Fetching elevations for %d nodes (batch size: %d)...", total_nodes, BATCH_SIZE)

    for batch_num, start in enumerate(range(0, len(lats), BATCH_SIZE)):
        if batch_num > 0:
            time.sleep(0.5)

        batch_lats = lats[start : start + BATCH_SIZE]
        batch_lons = lons[start : start + BATCH_SIZE]
        batch_elevations = _fetch_elevations_batch(batch_lats, batch_lons)

        if batch_elevations is None:
            logger.error("Failed to fetch elevations at batch %d. Graph will not be enriched.", batch_num)
            return

        elevations.extend(batch_elevations)
        progress = min(start + BATCH_SIZE, total_nodes)
        logger.info("Elevation progress: %d / %d nodes", progress, total_nodes)

    if len(elevations) != len(nodes):
        logger.error("Elevation count mismatch: got %d, expected %d", len(elevations), len(nodes))
        return

    for (node_id, _), elev in zip(nodes, elevations, strict=True):
        G.nodes[node_id]["elevation"] = elev

    logger.info("✓ Elevation enrichment complete: %d nodes with real topography", len(nodes))


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

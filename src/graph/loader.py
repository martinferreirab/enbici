"""Descarga, cachea y carga el grafo vial de Montevideo."""

from __future__ import annotations

import logging
from pathlib import Path

import networkx as nx
import osmnx as ox

from src.graph.elevation import enrich_graph_with_elevation, graph_has_elevation

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_CACHE_PATH = DATA_DIR / "montevideo.graphml"
PLACE_QUERY = "Montevideo, Uruguay"


def _configure_osm_tags() -> None:
    """Configure useful OSM tags before downloading graph."""
    tags = ox.settings.useful_tags_way.copy()
    bike_tags = [
        "cycleway",
        "cycleway:left",
        "cycleway:right",
        "cycleway:both",
        "bicycle",
    ]
    for tag in bike_tags:
        if tag not in tags:
            tags.append(tag)
    ox.settings.useful_tags_way = tags


def _download_graph() -> nx.MultiDiGraph:
    """Descarga el grafo ciclista de Montevideo desde OpenStreetMap."""
    logger.info("Descargando grafo OSM para '%s'...", PLACE_QUERY)
    _configure_osm_tags()
    return ox.graph_from_place(PLACE_QUERY, network_type="bike")


def _load_from_cache() -> nx.MultiDiGraph:
    """Carga el grafo desde el archivo GraphML cacheado."""
    logger.info("Cargando grafo cacheado: %s", GRAPH_CACHE_PATH)
    return ox.load_graphml(GRAPH_CACHE_PATH)


def _save_to_cache(G: nx.MultiDiGraph) -> None:
    """Persiste el grafo en disco como GraphML."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(G, GRAPH_CACHE_PATH)
    logger.info("Grafo guardado en caché: %s", GRAPH_CACHE_PATH)


def _graph_has_bikeways(G: nx.MultiDiGraph) -> bool:
    """Check if graph edges have is_dedicated_bikeway attribute."""
    if not G.edges():
        return False
    return any("is_dedicated_bikeway" in data for _, _, data in G.edges(data=True))


def _mark_bikeways(G: nx.MultiDiGraph) -> None:
    """Mark edges as dedicated bikeways based on OSM tags."""
    for u, v, _key, data in G.edges(keys=True, data=True):
        is_bikeway = False

        # Check for dedicated cycleway highway type
        highway = data.get("highway", "")
        if isinstance(highway, list):
            is_bikeway = "cycleway" in highway
        elif highway == "cycleway":
            is_bikeway = True

        # Check for cycleway tags
        if not is_bikeway:
            cycleway = data.get("cycleway", "")
            if isinstance(cycleway, list):
                is_bikeway = len(cycleway) > 0
            elif cycleway and cycleway not in ("no", "none"):
                is_bikeway = True

        # Check for cycleway:left/right/both
        if not is_bikeway:
            for side in ("left", "right", "both"):
                side_tag = f"cycleway:{side}"
                cycleway_side = data.get(side_tag, "")
                if isinstance(cycleway_side, list):
                    is_bikeway = len(cycleway_side) > 0
                elif cycleway_side and cycleway_side not in ("no", "none"):
                    is_bikeway = True
                    break

        # Check for bicycle=designated
        if not is_bikeway:
            bicycle = data.get("bicycle", "")
            if isinstance(bicycle, list):
                is_bikeway = "designated" in bicycle
            elif bicycle == "designated":
                is_bikeway = True

        data["is_dedicated_bikeway"] = is_bikeway


def load_montevideo_graph() -> nx.DiGraph:
    """
    Carga el grafo de Montevideo usando caché local si existe.

    En la primera ejecución descarga OSM, enriquece con elevación/pendiente
    y persiste ``data/montevideo.graphml``. Ejecuciones posteriores reutilizan
    exclusivamente el archivo cacheado.
    """
    if GRAPH_CACHE_PATH.exists():
        G = _load_from_cache()
    else:
        G = _download_graph()
        enrich_graph_with_elevation(G)
        _mark_bikeways(G)
        _save_to_cache(G)

    if not graph_has_elevation(G):
        enrich_graph_with_elevation(G)
        _save_to_cache(G)

    if not _graph_has_bikeways(G):
        _mark_bikeways(G)
        _save_to_cache(G)

    digraph = ox.convert.to_digraph(G)
    logger.info(
        "Grafo listo: %d nodos, %d aristas",
        digraph.number_of_nodes(),
        digraph.number_of_edges(),
    )
    return digraph

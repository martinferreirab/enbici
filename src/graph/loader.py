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


def _download_graph() -> nx.MultiDiGraph:
    """Descarga el grafo ciclista de Montevideo desde OpenStreetMap."""
    logger.info("Descargando grafo OSM para '%s'...", PLACE_QUERY)
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
        _save_to_cache(G)

    if not graph_has_elevation(G):
        enrich_graph_with_elevation(G)
        _save_to_cache(G)

    digraph = ox.convert.to_digraph(G)
    logger.info(
        "Grafo listo: %d nodos, %d aristas",
        digraph.number_of_nodes(),
        digraph.number_of_edges(),
    )
    return digraph

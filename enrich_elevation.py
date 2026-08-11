#!/usr/bin/env python3
"""One-time script to enrich montevideo.graphml with real elevation data from Open-Meteo."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import networkx as nx
import osmnx as ox

from src.graph.elevation import add_node_elevations, compute_edge_grades

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_CACHE_PATH = DATA_DIR / "montevideo.graphml"


def main() -> int:
    """Load graph, enrich with real elevations, and save."""
    if not GRAPH_CACHE_PATH.exists():
        logger.error("Graph cache not found at %s", GRAPH_CACHE_PATH)
        return 1

    logger.info("Loading graph from %s...", GRAPH_CACHE_PATH)
    G = ox.load_graphml(GRAPH_CACHE_PATH)
    logger.info("Loaded graph: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    logger.info("Starting elevation enrichment with Open-Meteo API...")
    add_node_elevations(G)

    logger.info("Computing edge grades...")
    compute_edge_grades(G)

    logger.info("Saving enriched graph to %s...", GRAPH_CACHE_PATH)
    ox.save_graphml(G, GRAPH_CACHE_PATH)

    logger.info("✓ Elevation enrichment complete!")
    sample_elevations = [float(G.nodes[node].get("elevation", 0)) for node in list(G.nodes())[:5]]
    logger.info("Sample elevations (first 5 nodes): %s", sample_elevations)

    return 0


if __name__ == "__main__":
    sys.exit(main())

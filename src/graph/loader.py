"""Descarga, cachea y carga el grafo vial de Montevideo."""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import networkx as nx
import osmnx as ox

from src.graph.elevation import enrich_graph_with_elevation, graph_has_elevation

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GRAPH_CACHE_PATH = DATA_DIR / "montevideo.graphml"
GRAPH_PICKLE_PATH = DATA_DIR / "montevideo_final.pkl"
PLACE_QUERY = "Montevideo, Uruguay"


def _configure_osm_tags() -> None:
    """Configure useful OSM tags before downloading graph."""
    pass


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


def _graph_has_park_paths(G: nx.MultiDiGraph) -> bool:
    """Check if graph edges have is_park_path attribute."""
    if not G.edges():
        return False
    return any("is_park_path" in data for _, _, data in G.edges(data=True))


def _mark_park_paths(G: nx.MultiDiGraph) -> None:
    """Mark edges as park/plaza internal paths based on OSM tags."""
    for u, v, _key, data in G.edges(keys=True, data=True):
        is_park_path = False

        highway = data.get("highway", "")
        if isinstance(highway, list):
            is_park_path = any(h in highway for h in ("footway", "path", "pedestrian"))
        elif highway in ("footway", "path", "pedestrian"):
            is_park_path = True

        data["is_park_path"] = is_park_path


MIN_PARK_CLUSTER_NODES = 3


def _inject_park_supernodes(G: nx.MultiDiGraph) -> None:
    """Add a virtual centroid super-node for each park/plaza path cluster.

    Groups edges already marked ``is_park_path`` (footway/path/pedestrian,
    see ``_mark_park_paths``) into connected components — each component is
    treated as one park/plaza. A virtual node is added at the component's
    centroid and connected bidirectionally to every perimeter node in it,
    letting routing "cut through" the park instead of only tracing its
    internal paths edge by edge.

    Idempotent: skips entirely if supernodes were already injected (detected
    via node id prefix), so calling it again on an already-processed graph
    is a no-op.
    """
    if any(str(n).startswith("park_supernode_") for n in G.nodes):
        logger.info("Park supernodes already present; skipping injection.")
        return

    park_subgraph = nx.Graph()
    park_subgraph.add_edges_from(
        (u, v)
        for u, v, data in G.edges(data=True)
        if data.get("is_park_path")
    )

    supernode_count = 0
    for component in nx.connected_components(park_subgraph):
        if len(component) < MIN_PARK_CLUSTER_NODES:
            continue

        centroid_lat = sum(G.nodes[n]["y"] for n in component) / len(component)
        centroid_lon = sum(G.nodes[n]["x"] for n in component) / len(component)

        supernode_id = f"park_supernode_{supernode_count}"
        supernode_count += 1
        G.add_node(supernode_id, y=centroid_lat, x=centroid_lon, elevation=0.0)

        for perimeter_node in component:
            perim_lat = G.nodes[perimeter_node]["y"]
            perim_lon = G.nodes[perimeter_node]["x"]
            length = ox.distance.great_circle(perim_lat, perim_lon, centroid_lat, centroid_lon)

            G.add_edge(
                perimeter_node, supernode_id,
                length=length, is_park_path=True, grade=0.0,
            )
            G.add_edge(
                supernode_id, perimeter_node,
                length=length, is_park_path=True, grade=0.0,
            )

    logger.info("Injected %d park/plaza super-nodes.", supernode_count)


def _add_against_traffic_edges(G: nx.MultiDiGraph) -> None:
    """Add reverse edges for oneway streets, tagged as against-traffic.

    Idempotent: clears any previously-added against-traffic edges first, so
    calling this repeatedly (e.g. on every load) never duplicates them.
    """
    existing_against_traffic = [
        (u, v, key)
        for u, v, key, data in G.edges(keys=True, data=True)
        if data.get("is_against_traffic", False)
    ]
    for u, v, key in existing_against_traffic:
        G.remove_edge(u, v, key)

    edges_to_add = []
    for u, v, key, data in G.edges(keys=True, data=True):
        oneway = data.get("oneway", False)
        if oneway is True or oneway == "yes":
            # This is a one-way street; create a reverse edge
            reverse_data = data.copy()
            reverse_data["is_against_traffic"] = True
            edges_to_add.append((v, u, reverse_data))

    for u, v, reverse_data in edges_to_add:
        G.add_edge(u, v, **reverse_data)


def _save_pickle_atomic(digraph: nx.DiGraph) -> None:
    """Persiste el DiGraph final como pickle binario, de forma atómica."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = GRAPH_PICKLE_PATH.with_suffix(".pkl.tmp")
    with tmp_path.open("wb") as f:
        pickle.dump(digraph, f)
    tmp_path.replace(GRAPH_PICKLE_PATH)
    logger.info("Grafo final guardado en caché binaria: %s", GRAPH_PICKLE_PATH)


def load_montevideo_graph() -> nx.DiGraph:
    """
    Carga el grafo de Montevideo, priorizando la caché binaria (pickle).

    FAST PATH: si ``montevideo_final.pkl`` existe, se carga directamente sin
    conversiones ni re-marcado de aristas (boot casi instantáneo).

    FALLBACK/BUILD PATH: si no existe el pickle, se carga (o descarga) el
    ``.graphml``, se enriquece con elevación/pendiente, se marcan park paths
    y against-traffic edges, se convierte a DiGraph, y el resultado final se
    persiste como pickle para que la próxima carga use el fast path.
    """
    if GRAPH_PICKLE_PATH.exists():
        with GRAPH_PICKLE_PATH.open("rb") as f:
            digraph = pickle.load(f)
        logger.info(
            "✓ Montevideo graph loaded from binary cache: %d nodes, %d edges",
            digraph.number_of_nodes(),
            digraph.number_of_edges(),
        )
        return digraph

    if GRAPH_CACHE_PATH.exists():
        G = _load_from_cache()
        # Graph already cached with elevations/grades; skip API calls
        if not graph_has_elevation(G):
            logger.warning("Cache missing elevation/grade data. Re-enrichment required.")
            enrich_graph_with_elevation(G)
            _save_to_cache(G)
    else:
        G = _download_graph()
        enrich_graph_with_elevation(G)
        _save_to_cache(G)

    _mark_park_paths(G)
    _inject_park_supernodes(G)
    _add_against_traffic_edges(G)

    digraph = ox.convert.to_digraph(G)
    logger.info(
        "✓ Montevideo graph built: %d nodes, %d edges",
        digraph.number_of_nodes(),
        digraph.number_of_edges(),
    )
    _save_pickle_atomic(digraph)
    return digraph

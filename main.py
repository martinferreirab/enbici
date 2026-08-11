#!/usr/bin/env python3
"""Script de validación Fase 1: ruteo con y sin penalización por elevación."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import compute_route_metrics, find_route, nearest_node
from src.visualization.map_export import export_route_map

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# Puntos reales en Montevideo
ORIGIN = (-34.9060, -56.1996)  # Plaza Independencia
DESTINATION = (-34.8947, -56.1520)  # Facultad de Ingeniería (UdelaR)

OUTPUT_DIR = ROOT / "output"


def _print_metrics(label: str, metrics) -> None:
    print(f"\n--- {label} (elevation_weight={metrics.elevation_weight}) ---")
    print(f"  Distancia total : {metrics.total_distance_m / 1000:.2f} km")
    print(f"  Desnivel acum.  : {metrics.total_elevation_gain_m:.1f} m")
    print(f"  Nodos en ruta   : {metrics.node_count}")


def main() -> None:
    logger.info("Cargando grafo de Montevideo...")
    graph = load_montevideo_graph()

    origin_node = nearest_node(graph, *ORIGIN)
    dest_node = nearest_node(graph, *DESTINATION)
    logger.info("Nodo origen=%s, destino=%s", origin_node, dest_node)

    route_distance = find_route(graph, origin_node, dest_node, elevation_weight=0.0)
    route_elevation = find_route(graph, origin_node, dest_node, elevation_weight=5.0)

    metrics_distance = compute_route_metrics(graph, route_distance, elevation_weight=0.0)
    metrics_elevation = compute_route_metrics(graph, route_elevation, elevation_weight=5.0)

    print("\n" + "=" * 52)
    print("  enbici — Comparativa de rutas Montevideo")
    print("  Plaza Independencia → Facultad de Ingeniería")
    print("=" * 52)

    _print_metrics("Ruta solo distancia", metrics_distance)
    _print_metrics("Ruta evitando repechos", metrics_elevation)

    delta_dist = metrics_elevation.total_distance_m - metrics_distance.total_distance_m
    delta_gain = metrics_elevation.total_elevation_gain_m - metrics_distance.total_elevation_gain_m
    print("\n--- Diferencia (elevación vs distancia) ---")
    print(f"  Δ distancia : {delta_dist:+.0f} m")
    print(f"  Δ desnivel  : {delta_gain:+.1f} m")

    map_path = export_route_map(
        graph,
        route_elevation,
        ORIGIN,
        DESTINATION,
        metrics_elevation,
        OUTPUT_DIR / "ruta_montevideo.html",
        title="Ruta con penalización por elevación",
    )
    print(f"\nMapa HTML guardado en: {map_path}")


if __name__ == "__main__":
    main()

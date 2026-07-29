"""Exportación de rutas a mapas HTML con Folium."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import folium
from branca.element import Element

if TYPE_CHECKING:
    from networkx import DiGraph

    from src.routing.pathfinder import RouteMetrics


def _path_coordinates(G: DiGraph, path: list[int]) -> list[tuple[float, float]]:
    """Convierte una secuencia de nodos a coordenadas (lat, lon)."""
    return [(G.nodes[node]["y"], G.nodes[node]["x"]) for node in path]


def export_route_map(
    G: DiGraph,
    path: list[int],
    origin: tuple[float, float],
    destination: tuple[float, float],
    metrics: RouteMetrics,
    output_path: Path | str,
    *,
    comparison_metrics: RouteMetrics | None = None,
    title: str = "Ruta enbici - Montevideo",
) -> Path:
    """
    Genera un mapa HTML interactivo con la ruta, marcadores y métricas.

    ``origin`` y ``destination`` son tuplas ``(lat, lon)``.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    coords = _path_coordinates(G, path)
    center_lat = sum(c[0] for c in coords) / len(coords)
    center_lon = sum(c[1] for c in coords) / len(coords)

    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="OpenStreetMap")

    folium.PolyLine(
        coords,
        color="#2563eb",
        weight=5,
        opacity=0.85,
        tooltip=f"Peso elevación: {metrics.elevation_weight}",
    ).add_to(fmap)

    folium.Marker(
        origin,
        popup="Origen",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(fmap)

    folium.Marker(
        destination,
        popup="Destino",
        icon=folium.Icon(color="red", icon="flag"),
    ).add_to(fmap)

    metrics_html = (
        f"<b>{title}</b><br>"
        f"Peso elevación: {metrics.elevation_weight}<br>"
        f"Distancia: {metrics.total_distance_m / 1000:.2f} km<br>"
        f"Desnivel +: {metrics.total_elevation_gain_m:.1f} m<br>"
        f"Nodos: {metrics.node_count}"
    )
    if comparison_metrics is not None:
        metrics_html += (
            f"<br><hr><b>Comparación (peso {comparison_metrics.elevation_weight})</b><br>"
            f"Distancia: {comparison_metrics.total_distance_m / 1000:.2f} km<br>"
            f"Desnivel +: {comparison_metrics.total_elevation_gain_m:.1f} m"
        )

    fmap.get_root().html.add_child(
        Element(
            f"""
            <div style="
                position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: white; padding: 12px 16px; border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.25); font-size: 13px;
                max-width: 320px;
            ">
                {metrics_html}
            </div>
            """
        )
    )

    fmap.save(str(output))
    return output

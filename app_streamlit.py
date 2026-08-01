#!/usr/bin/env python3
"""Interactive Streamlit UI for enbici — bike routing with elevation and wind weighting."""

from __future__ import annotations

import logging
from pathlib import Path

import folium
import streamlit as st
import streamlit_folium as stf

from src.api.weather import fetch_wind_data
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
from src.visualization.map_export import export_route_map

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="enbici — Bike Routing",
    page_icon="🚴",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚴 enbici — Rutas en bicicleta para Montevideo")
st.markdown(
    "Motor de ruteo con penalización por elevación y viento en tiempo real"
)

# Preset locations
PRESETS = {
    "Plaza Independencia": (-34.9060, -56.1996),
    "Facultad de Ingeniería": (-34.8947, -56.1520),
    "Pocitos": (-34.8879, -56.1747),
    "Cerro de Montevideo": (-34.8555, -56.2007),
    "Puerto Viejo": (-34.9118, -56.2147),
}

# Load graph once with caching
@st.cache_resource
def load_graph():
    """Load and cache the Montevideo graph."""
    logger.info("Loading Montevideo graph...")
    return load_montevideo_graph()


# Sidebar for input controls
with st.sidebar:
    st.header("⚙️ Parámetros de Ruta")

    # Preset location buttons
    st.subheader("Ubicaciones Predefinidas")
    col1, col2 = st.columns(2)

    origin_preset = None
    dest_preset = None

    if col1.button("Plaza Ind. → Fac. Ing.", use_container_width=True):
        origin_preset = PRESETS["Plaza Independencia"]
        dest_preset = PRESETS["Facultad de Ingeniería"]

    if col2.button("Pocitos → Cerro", use_container_width=True):
        origin_preset = PRESETS["Pocitos"]
        dest_preset = PRESETS["Cerro de Montevideo"]

    if col1.button("Puerto Viejo → Pocitos", use_container_width=True):
        origin_preset = PRESETS["Puerto Viejo"]
        dest_preset = PRESETS["Pocitos"]

    st.divider()

    # Manual coordinate input
    st.subheader("Coordenadas Personalizadas")

    origin_lat = st.number_input(
        "Latitud Origen",
        value=origin_preset[0] if origin_preset else -34.9060,
        format="%.4f",
        step=0.0001,
    )
    origin_lon = st.number_input(
        "Longitud Origen",
        value=origin_preset[1] if origin_preset else -56.1996,
        format="%.4f",
        step=0.0001,
    )

    st.divider()

    dest_lat = st.number_input(
        "Latitud Destino",
        value=dest_preset[0] if dest_preset else -34.8947,
        format="%.4f",
        step=0.0001,
    )
    dest_lon = st.number_input(
        "Longitud Destino",
        value=dest_preset[1] if dest_preset else -56.1520,
        format="%.4f",
        step=0.0001,
    )

    st.divider()

    # Weight sliders
    st.subheader("Pesos de Ruteo")
    elevation_weight = st.slider(
        "Penalización por Elevación",
        min_value=0.0,
        max_value=10.0,
        value=5.0,
        step=0.5,
        help="Mayor valor = evita más subidas",
    )

    wind_weight = st.slider(
        "Penalización por Viento",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.5,
        help="0 = sin viento, >0 = considera viento actual",
    )

    bikeway_weight = st.slider(
        "Preferencia por Ciclovías",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.5,
        help="0 = indiferente, >0 = prefiere ciclovías dedicadas",
    )

    st.divider()

    # Calculate button
    calculate_button = st.button(
        "🗺️ Calcular Ruta", use_container_width=True, type="primary"
    )

# Main content area
if calculate_button:
    # Load graph
    graph = load_graph()

    # Show status
    with st.spinner("Calculando ruta..."):
        try:
            # Find nearest nodes
            origin_node = nearest_node(graph, origin_lat, origin_lon)
            dest_node = nearest_node(graph, dest_lat, dest_lon)

            if origin_node == dest_node:
                st.error("❌ El origen y destino son el mismo punto")
            else:
                # Fetch wind data if needed
                wind_data = None
                if wind_weight > 0:
                    wind_data = fetch_wind_data()

                # Find route
                path = find_route(
                    graph,
                    origin_node,
                    dest_node,
                    elevation_weight=elevation_weight,
                    wind_data=wind_data,
                    wind_weight=wind_weight,
                    bikeway_weight=bikeway_weight,
                )

                if path:
                    # Compute metrics
                    metrics = compute_route_metrics(
                        graph,
                        path,
                        elevation_weight=elevation_weight,
                        wind_data=wind_data,
                        wind_weight=wind_weight,
                        bikeway_weight=bikeway_weight,
                    )

                    # Display metrics
                    st.success("✅ Ruta calculada exitosamente")

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric(
                            "📏 Distancia",
                            f"{metrics.total_distance_m / 1000:.2f} km",
                        )

                    with col2:
                        st.metric(
                            "⛰️ Desnivel",
                            f"{metrics.total_elevation_gain_m:.0f} m",
                        )

                    with col3:
                        st.metric(
                            "🚩 Nodos",
                            f"{metrics.node_count}",
                        )

                    with col4:
                        if wind_data:
                            st.metric(
                                "💨 Viento",
                                f"{wind_data.speed_ms:.1f} m/s",
                                f"{wind_data.direction_degrees:.0f}°",
                            )
                        else:
                            st.metric("💨 Viento", "N/A")

                    st.divider()

                    # Wind metrics if available
                    if wind_data and wind_weight > 0:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(
                                f"**Dirección del viento**: {wind_data.direction_degrees:.0f}° "
                                f"({'N' if 337.5 <= wind_data.direction_degrees or wind_data.direction_degrees < 22.5 else 'NE' if 22.5 <= wind_data.direction_degrees < 67.5 else 'E' if 67.5 <= wind_data.direction_degrees < 112.5 else 'SE' if 112.5 <= wind_data.direction_degrees < 157.5 else 'S' if 157.5 <= wind_data.direction_degrees < 202.5 else 'SW' if 202.5 <= wind_data.direction_degrees < 247.5 else 'W' if 247.5 <= wind_data.direction_degrees < 292.5 else 'NW'})"
                            )
                        with col2:
                            st.info(
                                f"**Factor de viento de frente**: {metrics.average_headwind_factor:.1%} "
                                f"({'Tailwind ↗️' if metrics.average_headwind_factor < 0.33 else 'Mixed' if metrics.average_headwind_factor < 0.66 else 'Headwind ↙️'})"
                            )

                    # Bikeway metrics
                    if bikeway_weight > 0:
                        st.info(
                            f"**Ciclovías en la ruta**: {metrics.bikeway_percentage:.1f}% "
                            f"({'🚴 Muchas ciclovías' if metrics.bikeway_percentage >= 50 else '🚴 Algunas ciclovías' if metrics.bikeway_percentage >= 20 else '🚗 Pocas ciclovías'})"
                        )

                    st.divider()

                    # Generate and display map
                    st.subheader("🗺️ Mapa de la Ruta")

                    # Create folium map
                    route_coords = [
                        (graph.nodes[node]["y"], graph.nodes[node]["x"])
                        for node in path
                    ]

                    # Center map on route midpoint
                    center_lat = sum(c[0] for c in route_coords) / len(
                        route_coords
                    )
                    center_lon = sum(c[1] for c in route_coords) / len(
                        route_coords
                    )

                    m = folium.Map(
                        location=[center_lat, center_lon],
                        zoom_start=13,
                        tiles="OpenStreetMap",
                    )

                    # Add route polyline
                    folium.PolyLine(
                        route_coords,
                        color="blue",
                        weight=3,
                        opacity=0.8,
                        popup="Ruta calculada",
                    ).add_to(m)

                    # Add origin marker
                    folium.Marker(
                        location=(origin_lat, origin_lon),
                        popup="Origen",
                        icon=folium.Icon(color="green", icon="play"),
                    ).add_to(m)

                    # Add destination marker
                    folium.Marker(
                        location=(dest_lat, dest_lon),
                        popup="Destino",
                        icon=folium.Icon(color="red", icon="stop"),
                    ).add_to(m)

                    # Display map in streamlit
                    stf.folium_static(m, width=1200, height=600)

                    # Export and save HTML map
                    map_path = "output/ruta_streamlit.html"
                    export_route_map(
                        graph,
                        path,
                        (origin_lat, origin_lon),
                        (dest_lat, dest_lon),
                        metrics,
                        map_path,
                    )

                    st.success(f"✅ Mapa guardado en {map_path}")

                else:
                    st.error("❌ No se encontró ruta entre los puntos")

        except Exception as e:
            st.error(f"❌ Error al calcular ruta: {str(e)}")
            logger.exception("Routing error")

else:
    # Show welcome message
    st.info(
        """
    👈 **Usa el panel lateral** para:
    1. Seleccionar ubicaciones predefinidas O ingresar coordenadas personalizadas
    2. Ajustar los pesos de elevación y viento
    3. Hacer clic en "Calcular Ruta"

    **Parámetros:**
    - **Elevación**: Mayor valor evita más subidas (0-10)
    - **Viento**: Considera la dirección actual del viento (0-10)
    """
    )

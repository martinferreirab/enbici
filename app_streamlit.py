#!/usr/bin/env python3
"""Interactive Streamlit UI for enbici — bike routing with elevation and wind weighting."""

from __future__ import annotations

import logging
from pathlib import Path

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.api.weather import fetch_wind_data
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
from src.utils.geocoding import geocode_place
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


def _get_wind_cardinal(degrees: float) -> str:
    """Convert wind direction in degrees to cardinal direction."""
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round((degrees % 360) / 22.5) % 16
    return directions[idx]


# Initialize session state for coordinates and calculated route
if "origin_coords" not in st.session_state:
    st.session_state.origin_coords = None
if "dest_coords" not in st.session_state:
    st.session_state.dest_coords = None
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None
if "last_route_key" not in st.session_state:
    st.session_state.last_route_key = None


# Sidebar for input controls
with st.sidebar:
    st.header("⚙️ Parámetros de Ruta")

    # Preset location buttons
    st.subheader("🏠 Ubicaciones Predefinidas")
    col1, col2 = st.columns(2)

    if col1.button("Plaza Ind. → Fac. Ing.", use_container_width=True):
        st.session_state.origin_coords = PRESETS["Plaza Independencia"]
        st.session_state.dest_coords = PRESETS["Facultad de Ingeniería"]
        st.success("✅ Preset cargado")

    if col2.button("Pocitos → Cerro", use_container_width=True):
        st.session_state.origin_coords = PRESETS["Pocitos"]
        st.session_state.dest_coords = PRESETS["Cerro de Montevideo"]
        st.success("✅ Preset cargado")

    if col1.button("Puerto Viejo → Pocitos", use_container_width=True):
        st.session_state.origin_coords = PRESETS["Puerto Viejo"]
        st.session_state.dest_coords = PRESETS["Pocitos"]
        st.success("✅ Preset cargado")

    st.divider()

    # Place name search (geocoding)
    st.subheader("🔍 Búsqueda por Nombre")

    origin_place = st.text_input(
        "Ubicación Origen",
        placeholder="ej: Plaza Independencia, Pocitos",
    )

    if origin_place and st.button("🔎 Geocodificar Origen", key="geocode_origin"):
        coords = geocode_place(origin_place)
        if coords:
            st.session_state.origin_coords = (coords.lat, coords.lon)
            st.success(f"✅ {origin_place} ({coords.lat:.4f}, {coords.lon:.4f})")
        else:
            st.error(f"❌ No se encontró: {origin_place}")

    dest_place = st.text_input(
        "Ubicación Destino",
        placeholder="ej: Cerro, Facultad de Ingeniería",
    )

    if dest_place and st.button("🔎 Geocodificar Destino", key="geocode_dest"):
        coords = geocode_place(dest_place)
        if coords:
            st.session_state.dest_coords = (coords.lat, coords.lon)
            st.success(f"✅ {dest_place} ({coords.lat:.4f}, {coords.lon:.4f})")
        else:
            st.error(f"❌ No se encontró: {dest_place}")

    st.divider()

    # Display current coordinates
    if st.session_state.origin_coords or st.session_state.dest_coords:
        st.caption("📍 Ubicaciones Cargadas:")
        if st.session_state.origin_coords:
            st.caption(f"🟢 Origen: {st.session_state.origin_coords[0]:.4f}, {st.session_state.origin_coords[1]:.4f}")
        if st.session_state.dest_coords:
            st.caption(f"🔴 Destino: {st.session_state.dest_coords[0]:.4f}, {st.session_state.dest_coords[1]:.4f}")

        st.divider()

    # Weight sliders
    st.subheader("⚖️ Pesos de Ruteo")
    elevation_weight = st.slider(
        "Elevación",
        min_value=0.0,
        max_value=10.0,
        value=5.0,
        step=0.5,
        help="Mayor valor = evita más subidas",
    )

    wind_weight = st.slider(
        "Viento",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.5,
        help="0 = sin viento, >0 = considera viento actual",
    )

    bikeway_weight = st.slider(
        "Ciclovías",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.5,
        help="0 = indiferente, >0 = prefiere ciclovías dedicadas",
    )

    # Clear route if weights change (to avoid showing old metrics with new weights)
    current_route_key = f"route_{st.session_state.origin_coords}_{st.session_state.dest_coords}_{elevation_weight}_{wind_weight}_{bikeway_weight}"
    if st.session_state.last_route_key and st.session_state.last_route_key != current_route_key:
        st.session_state.calculated_route = None
    st.session_state.last_route_key = current_route_key

    st.divider()

    # Calculate button
    has_coords = st.session_state.origin_coords and st.session_state.dest_coords
    if not has_coords:
        st.warning("⚠️ Carga origen y destino para calcular")
        st.button("🗺️ Calcular Ruta", use_container_width=True, type="primary", disabled=True)
        calculate_button = False
    else:
        calculate_button = st.button(
            "🗺️ Calcular Ruta", use_container_width=True, type="primary"
        )

# Handle button click: calculate route and store in session state
if calculate_button:
    graph = load_graph()
    origin_lat, origin_lon = st.session_state.origin_coords
    dest_lat, dest_lon = st.session_state.dest_coords

    with st.spinner("Calculando ruta..."):
        try:
            origin_node = nearest_node(graph, origin_lat, origin_lon)
            dest_node = nearest_node(graph, dest_lat, dest_lon)

            if origin_node == dest_node:
                st.error("❌ El origen y destino son el mismo punto")
            else:
                wind_data = None
                if wind_weight > 0:
                    wind_data = fetch_wind_data()

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
                    metrics = compute_route_metrics(
                        graph,
                        path,
                        elevation_weight=elevation_weight,
                        wind_data=wind_data,
                        wind_weight=wind_weight,
                        bikeway_weight=bikeway_weight,
                    )

                    # Store route data in session state for persistence across re-runs
                    st.session_state.calculated_route = {
                        "path": path,
                        "metrics": metrics,
                        "origin_lat": origin_lat,
                        "origin_lon": origin_lon,
                        "dest_lat": dest_lat,
                        "dest_lon": dest_lon,
                        "wind_data": wind_data,
                        "elevation_weight": elevation_weight,
                        "wind_weight": wind_weight,
                        "bikeway_weight": bikeway_weight,
                        "map_key": f"map_{origin_lat:.4f}_{origin_lon:.4f}_{dest_lat:.4f}_{dest_lon:.4f}_{elevation_weight}_{wind_weight}_{bikeway_weight}",
                    }

                    st.success("✅ Ruta calculada exitosamente")
                else:
                    st.error("❌ No se encontró ruta entre los puntos")

        except Exception as e:
            st.error(f"❌ Error al calcular ruta: {str(e)}")
            logger.exception("Routing error")

# Display calculated route if it exists (persists across re-runs)
if st.session_state.calculated_route:
    route_data = st.session_state.calculated_route
    metrics = route_data["metrics"]
    path = route_data["path"]
    wind_data = route_data["wind_data"]
    origin_lat = route_data["origin_lat"]
    origin_lon = route_data["origin_lon"]
    dest_lat = route_data["dest_lat"]
    dest_lon = route_data["dest_lon"]
    map_key = route_data["map_key"]

    # Display metrics
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
        if wind_data and route_data["wind_weight"] > 0:
            wind_dir_cardinal = _get_wind_cardinal(wind_data.direction_degrees)
            st.metric(
                "💨 Viento",
                f"{wind_data.speed_ms:.1f} m/s",
                f"{wind_data.direction_degrees:.0f}° {wind_dir_cardinal}",
            )
        else:
            st.metric("💨 Viento", "—" if route_data["wind_weight"] == 0 else "N/A")

    st.divider()

    # Wind metrics if available
    if wind_data and route_data["wind_weight"] > 0:
        col1, col2 = st.columns(2)
        wind_cardinal = _get_wind_cardinal(wind_data.direction_degrees)
        with col1:
            st.info(
                f"**Dirección del viento**: {wind_data.direction_degrees:.0f}° ({wind_cardinal})"
            )
        with col2:
            headwind_type = "Tailwind ↗️" if metrics.average_headwind_factor < 0.33 else "Mixed" if metrics.average_headwind_factor < 0.66 else "Headwind ↙️"
            st.info(
                f"**Factor de viento de frente**: {metrics.average_headwind_factor:.1%} ({headwind_type})"
            )

    # Bikeway metrics
    if route_data["bikeway_weight"] > 0:
        st.info(
            f"**Ciclovías en la ruta**: {metrics.bikeway_percentage:.1f}% "
            f"({'🚴 Muchas ciclovías' if metrics.bikeway_percentage >= 50 else '🚴 Algunas ciclovías' if metrics.bikeway_percentage >= 20 else '🚗 Pocas ciclovías'})"
        )

    st.divider()

    # Generate and display map
    st.subheader("🗺️ Mapa de la Ruta")

    graph = load_graph()
    route_coords = [
        (graph.nodes[node]["y"], graph.nodes[node]["x"])
        for node in path
    ]

    center_lat = sum(c[0] for c in route_coords) / len(route_coords)
    center_lon = sum(c[1] for c in route_coords) / len(route_coords)

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
    )

    folium.PolyLine(
        route_coords,
        color="blue",
        weight=3,
        opacity=0.8,
        popup="Ruta calculada",
    ).add_to(m)

    folium.Marker(
        location=(origin_lat, origin_lon),
        popup="Origen",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(m)

    folium.Marker(
        location=(dest_lat, dest_lon),
        popup="Destino",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(m)

    st_folium(m, width=1200, height=600, key=map_key)

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
    # Show welcome message
    st.info(
        """
    👈 **Usa el panel lateral** para:
    1. **Presets rápidos**: Haz clic en un botón predefinido (Plaza Ind. → Fac. Ing., etc.)
    2. **O busca por nombre**: Ingresa "Plaza Independencia", "Cerro", etc. y geocodifica
    3. Ajusta los pesos de elevación, viento y ciclovías
    4. Haz clic en "Calcular Ruta"

    **Parámetros:**
    - **Elevación**: Mayor valor evita más subidas (0-10)
    - **Viento**: Considera la dirección actual del viento (0-10)
    - **Ciclovías**: Prefiere rutas con ciclovías dedicadas (0-10)
    """
    )

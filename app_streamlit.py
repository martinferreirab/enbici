#!/usr/bin/env python3
"""Interactive Streamlit UI for enbici — bike routing with elevation and wind weighting."""

from __future__ import annotations

import logging
import os
import threading

import folium
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit_folium import st_folium

from src.api.weather import fetch_wind_data
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
from src.utils.geocoding import geocode_place
from src.visualization.map_export import export_route_map

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = os.getenv("ENBICI_API_URL", "http://localhost:8000")

# Plaza Independencia (Montevideo): fixed position used to mock GPS telemetry
MOCK_LAT, MOCK_LON = -34.9060, -56.1996
TELEMETRY_INTERVAL_S = 15

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


def _mock_telemetry_loop(stop: threading.Event, token: str, journey_id: int) -> None:
    """Background thread: POST the fixed mock position every 15 s until `stop` is set.

    Must not touch st.session_state (no script-run context in this thread).
    """
    headers = {"Authorization": f"Bearer {token}"}
    while not stop.is_set():
        try:
            requests.post(
                f"{API_URL}/users/me/routes/{journey_id}/telemetry",
                json={"lat": MOCK_LAT, "lon": MOCK_LON, "speed_ms": 0.0},
                headers=headers,
                timeout=10,
            )
        except requests.RequestException:
            logger.warning("Mock telemetry POST failed", exc_info=True)
        stop.wait(TELEMETRY_INTERVAL_S)


def _stop_mock_telemetry() -> None:
    stop = st.session_state.get("mock_stop")
    if stop:
        stop.set()
    st.session_state.mock_stop = None


# Initialize session state for coordinates and calculated route
if "origin_coords" not in st.session_state:
    st.session_state.origin_coords = None
if "dest_coords" not in st.session_state:
    st.session_state.dest_coords = None
if "calculated_route" not in st.session_state:
    st.session_state.calculated_route = None
if "last_route_key" not in st.session_state:
    st.session_state.last_route_key = None
if "saved_journey_id" not in st.session_state:
    st.session_state.saved_journey_id = None
if "mock_stop" not in st.session_state:
    st.session_state.mock_stop = None
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None


def _api_error(resp: requests.Response) -> str:
    """Extract a readable error message from a FastAPI error response."""
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):  # pydantic validation errors
        detail = "; ".join(str(d.get("msg", d)) for d in detail)
    return str(detail or f"HTTP {resp.status_code}")


def _auth(endpoint: str, username: str, password: str) -> None:
    """POST credentials to /login or /register and store the session on success."""
    try:
        resp = requests.post(
            f"{API_URL}/{endpoint}",
            json={"username": username, "password": password},
            timeout=10,
        )
    except requests.RequestException as e:
        st.error(f"❌ No se pudo conectar con el servidor: {e}")
        return
    if resp.ok:
        data = resp.json()
        st.session_state.token = data["access_token"]
        st.session_state.username = data["username"]
        st.rerun()
    else:
        st.error(f"❌ {_api_error(resp)}")


# Sidebar for input controls
with st.sidebar:
    st.header("👤 Cuenta")
    if st.session_state.token:
        st.success(f"Bienvenido, {st.session_state.username} 👋")
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.token = None
            st.session_state.username = None
            st.rerun()
    else:
        login_tab, register_tab = st.tabs(["Iniciar Sesión", "Registrarse"])
        with login_tab:
            with st.form("login_form"):
                login_user = st.text_input("Usuario", key="login_user")
                login_pass = st.text_input("Contraseña", type="password", key="login_pass")
                if st.form_submit_button("Entrar", use_container_width=True):
                    _auth("login", login_user, login_pass)
        with register_tab:
            with st.form("register_form"):
                reg_user = st.text_input("Usuario", key="reg_user", help="Mínimo 3 caracteres")
                reg_pass = st.text_input("Contraseña", type="password", key="reg_pass", help="Mínimo 6 caracteres")
                if st.form_submit_button("Crear cuenta", use_container_width=True):
                    _auth("register", reg_user, reg_pass)

    st.divider()
    st.header("⚙️ Parámetros de Ruta")

    st.subheader("🔍 Búsqueda por Nombre")

    origin_place = st.text_input(
        "Ubicación Origen",
        placeholder="ej: Plaza Independencia, Pocitos",
    )

    if origin_place and st.button("🔎 Geocodificar Origen", key="geocode_origin"):
        coords = geocode_place(origin_place)
        if coords:
            st.session_state.origin_coords = (coords.lat, coords.lon)
            st.success(f"✅ {origin_place}")
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
            st.success(f"✅ {dest_place}")
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

    allow_parks = st.checkbox(
        "Atravesar parques y plazas",
        value=True,
        help="Permite usar senderos internos de áreas verdes",
    )

    max_against_traffic_blocks = st.selectbox(
        "Tolerancia a contramano",
        options=[0, 1, 2, 3],
        index=0,
        format_func=lambda x: "Deshabilitado" if x == 0 else f"{x} bloque(s)",
        help="Máximo de cuadras permitidas en sentido contrario (0-3)",
    )

    # Clear route if weights change (to avoid showing old metrics with new weights)
    current_route_key = f"route_{st.session_state.origin_coords}_{st.session_state.dest_coords}_{elevation_weight}_{wind_weight}_{allow_parks}_{max_against_traffic_blocks}"
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
                    allow_parks=allow_parks,
                    max_against_traffic_blocks=max_against_traffic_blocks,
                )

                if path:
                    metrics = compute_route_metrics(
                        graph,
                        path,
                        elevation_weight=elevation_weight,
                        wind_data=wind_data,
                        wind_weight=wind_weight,
                        allow_parks=allow_parks,
                        max_against_traffic_blocks=max_against_traffic_blocks,
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
                        "origin_place": origin_place.strip() or f"{origin_lat:.4f}, {origin_lon:.4f}",
                        "dest_place": dest_place.strip() or f"{dest_lat:.4f}, {dest_lon:.4f}",
                        "elevation_weight": elevation_weight,
                        "wind_weight": wind_weight,
                        "allow_parks": allow_parks,
                        "max_against_traffic_blocks": max_against_traffic_blocks,
                        "map_key": f"map_{origin_lat:.4f}_{origin_lon:.4f}_{dest_lat:.4f}_{dest_lon:.4f}_{elevation_weight}_{wind_weight}_{allow_parks}_{max_against_traffic_blocks}",
                    }

                    _stop_mock_telemetry()
                    st.session_state.saved_journey_id = None
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

    graph = load_graph()
    route_coords = [
        (graph.nodes[node]["y"], graph.nodes[node]["x"])
        for node in path
    ]

    center_lat = sum(c[0] for c in route_coords) / len(route_coords)
    center_lon = sum(c[1] for c in route_coords) / len(route_coords)

    # 1. Interactive Folium Map
    st.subheader("🗺️ Mapa de la Ruta")

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=13,
        tiles="OpenStreetMap",
    )

    # Route (blue)
    folium.PolyLine(
        route_coords,
        color="#2563eb",
        weight=5,
        opacity=0.85,
        popup="Ruta",
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

    st.divider()

    # 2. Route Metrics
    st.subheader("📊 Métricas de Ruta")

    col1, col2, col3 = st.columns(3)
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
        if wind_data and route_data["wind_weight"] > 0:
            # Extract representative wind data from WindGrid
            representative_wind = next(iter(wind_data.points.values()), None) if wind_data.points else None
            if representative_wind:
                wind_dir_cardinal = _get_wind_cardinal(representative_wind.direction_degrees)
                st.metric(
                    "💨 Viento",
                    f"{representative_wind.speed_ms:.1f} m/s",
                    f"{representative_wind.direction_degrees:.0f}° {wind_dir_cardinal}",
                )
            else:
                st.metric("💨 Viento", "N/A")
        else:
            st.metric("💨 Viento", "—" if route_data["wind_weight"] == 0 else "N/A")

    # Save route (requires login)
    logged_in = bool(st.session_state.token)
    if st.button(
        "💾 Guardar Ruta",
        disabled=not logged_in,
        help=None if logged_in else "Inicia sesión para guardar rutas",
    ):
        payload = {
            "origin_place": route_data["origin_place"],
            "dest_place": route_data["dest_place"],
            "distance_km": metrics.total_distance_m / 1000,
            "elevation_gain_m": metrics.total_elevation_gain_m,
            "elevation_weight": route_data["elevation_weight"],
            "wind_weight": route_data["wind_weight"],
            "allow_parks": route_data["allow_parks"],
            "max_against_traffic_blocks": route_data["max_against_traffic_blocks"],
        }
        try:
            resp = requests.post(
                f"{API_URL}/users/me/routes",
                json=payload,
                headers={"Authorization": f"Bearer {st.session_state.token}"},
                timeout=10,
            )
            if resp.ok:
                st.session_state.saved_journey_id = resp.json()["id"]
                st.success("✅ Ruta guardada")
            elif resp.status_code == 401:
                st.session_state.token = None
                st.session_state.username = None
                st.error("❌ Sesión expirada, inicia sesión nuevamente")
            else:
                st.error(f"❌ No se pudo guardar: {_api_error(resp)}")
        except requests.RequestException as e:
            st.error(f"❌ No se pudo conectar con el servidor: {e}")

    # Mock journey start (only once the journey has been saved)
    if st.session_state.saved_journey_id and logged_in:
        journey_id = st.session_state.saved_journey_id
        mock_running = st.session_state.mock_stop is not None and not st.session_state.mock_stop.is_set()
        if mock_running:
            st.info(f"📡 Simulando telemetría en Plaza Independencia cada {TELEMETRY_INTERVAL_S}s (viaje #{journey_id})")
            if st.button("⏹️ Detener Simulación"):
                _stop_mock_telemetry()
                st.rerun()
        elif st.button("▶️ Simular Inicio de Ruta"):
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            try:
                resp = requests.post(f"{API_URL}/users/me/routes/{journey_id}/start", headers=headers, timeout=10)
                if resp.ok:
                    stop = threading.Event()
                    threading.Thread(
                        target=_mock_telemetry_loop,
                        args=(stop, st.session_state.token, journey_id),
                        daemon=True,
                    ).start()
                    st.session_state.mock_stop = stop
                    st.rerun()
                else:
                    st.error(f"❌ No se pudo iniciar: {_api_error(resp)}")
            except requests.RequestException as e:
                st.error(f"❌ No se pudo conectar con el servidor: {e}")

    # Wind metrics if available
    if wind_data and route_data["wind_weight"] > 0:
        representative_wind = next(iter(wind_data.points.values()), None) if wind_data.points else None
        if representative_wind:
            col1, col2 = st.columns(2)
            wind_cardinal = _get_wind_cardinal(representative_wind.direction_degrees)
            with col1:
                st.info(
                    f"**Dirección del viento**: {representative_wind.direction_degrees:.0f}° ({wind_cardinal})"
                )
            with col2:
                headwind_type = "Tailwind ↗️" if metrics.average_headwind_factor < 0.33 else "Mixed" if metrics.average_headwind_factor < 0.66 else "Headwind ↙️"
                st.info(
                    f"**Factor de viento de frente**: {metrics.average_headwind_factor:.1%} ({headwind_type})"
                )

    st.divider()

    # 3. Elevation Profile Chart
    st.subheader("📈 Perfil de Elevación")

    elevations = [graph.nodes[node].get("elevation", 0.0) for node in path]

    # Calculate cumulative distance
    distances_cumulative = [0.0]
    cumulative = 0.0
    for u, v in zip(path[:-1], path[1:], strict=True):
        edge_data = graph.edges[u, v]
        length = edge_data.get("length", 0.0)
        cumulative += length
        distances_cumulative.append(cumulative)

    # Convert to kilometers
    distances_km = [d / 1000.0 for d in distances_cumulative]

    # Create elevation profile chart
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=distances_km,
            y=elevations,
            mode="lines",
            name="Elevación",
            line=dict(color="rgb(31, 119, 180)", width=2),
            fill="tozeroy",
            fillcolor="rgba(31, 119, 180, 0.2)",
        )
    )
    fig.update_layout(
        title="Perfil de Elevación vs Distancia",
        xaxis_title="Distancia (km)",
        yaxis_title="Elevación (m)",
        hovermode="x unified",
        template="plotly_white",
        height=400,
    )
    st.plotly_chart(fig, use_container_width=True, key=f"elevation_profile_{map_key}")

    # Export map
    map_path = "output/ruta_streamlit.html"
    export_route_map(
        graph,
        path,
        (origin_lat, origin_lon),
        (dest_lat, dest_lon),
        metrics,
        map_path,
    )

else:
    # Show welcome message
    st.info(
        """
    👈 **Usa el panel lateral** para:
    1. Busca una ubicación por nombre ("Plaza Independencia", "Cerro", etc.) y geocodifica
    2. Ajusta los pesos de elevación y viento
    3. Haz clic en "Calcular Ruta"

    **Parámetros:**
    - **Elevación**: Mayor valor evita más subidas (0-10)
    - **Viento**: Considera la dirección actual del viento (0-10)
    - **Parques y plazas**: Permite/deniega senderos internos de áreas verdes
    """
    )

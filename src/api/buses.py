"""Cliente de posiciones de ómnibus en tiempo real de la Intendencia de Montevideo."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import TYPE_CHECKING

import networkx as nx
import osmnx as ox
import requests
from pyproj import Transformer

if TYPE_CHECKING:
    from networkx import DiGraph

logger = logging.getLogger(__name__)

TOKEN_URL = (
    "https://mvdapi-auth.montevideo.gub.uy"
    "/auth/realms/pci/protocol/openid-connect/token"
)
BUSES_URL = "https://api.montevideo.gub.uy/api/transportepublico/buses"
BUS_CACHE_SECONDS = 60
MAX_POSITION_AGE_SECONDS = 300
MAX_BUS_TO_EDGE_DISTANCE_M = 30.0
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BusApiError(RuntimeError):
    """Raised when live bus data cannot be retrieved or matched."""


@dataclass(frozen=True)
class BusPosition:
    """A fresh bus position in WGS84 coordinates."""

    longitude: float
    latitude: float


@dataclass(frozen=True)
class BusTraffic:
    """Live bus counts assigned to graph edges."""

    edge_counts: dict[tuple[int, int], int]
    fresh_positions: int
    matched_positions: int
    fetched_at: datetime


_cache_lock = threading.Lock()
_token: str | None = None
_token_expires_at = 0.0
_traffic_cache: BusTraffic | None = None
_traffic_cache_graph_id: int | None = None
_traffic_cache_expires_at = 0.0


def _client_credentials() -> tuple[str, str]:
    client_id = os.getenv("MONTEVIDEO_CLIENT_ID")
    client_secret = os.getenv("MONTEVIDEO_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise BusApiError(
            "Faltan MONTEVIDEO_CLIENT_ID y MONTEVIDEO_CLIENT_SECRET; "
            "configuralos como variables de entorno para usar el tránsito en vivo."
        )
    return client_id, client_secret


def _get_access_token() -> str:
    global _token, _token_expires_at

    client_id, client_secret = _client_credentials()
    if _token and time.monotonic() < _token_expires_at:
        return _token

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        token_data = response.json()
    except (requests.RequestException, ValueError) as exc:
        response = getattr(exc, "response", None)
        details = f": {response.text[:300]}" if response is not None and response.text else ""
        raise BusApiError(
            f"No se pudo autenticar con la API de la IM: {exc}{details}"
        ) from exc

    if not isinstance(token_data, dict):
        raise BusApiError("La API de autenticación devolvió una respuesta inválida.")
    access_token = token_data.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise BusApiError("La API de autenticación no devolvió un access_token.")

    try:
        expires_in = max(1, int(token_data.get("expires_in", 3600)))
    except (TypeError, ValueError) as exc:
        raise BusApiError("La API devolvió una duración de token inválida.") from exc

    _token = access_token
    _token_expires_at = time.monotonic() + expires_in - min(30, expires_in // 10)
    return access_token


def _parse_fresh_bus_positions(payload: object) -> list[BusPosition]:
    if not isinstance(payload, list):
        raise BusApiError("La API de buses devolvió una respuesta que no es una lista.")

    now = datetime.now(timezone.utc)
    positions: list[BusPosition] = []
    skipped = 0

    for item in payload:
        if not isinstance(item, dict):
            skipped += 1
            continue
        vehicle_type = item.get("vehicleType")
        entity_type = item.get("eType")
        if vehicle_type not in (None, "bus") or entity_type not in (None, "buses"):
            continue

        location = item.get("location")
        coordinates = location.get("coordinates") if isinstance(location, dict) else None
        timestamp = item.get("timestamp")
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            skipped += 1
            continue

        try:
            observed_at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            longitude, latitude = float(coordinates[0]), float(coordinates[1])
        except (TypeError, ValueError):
            skipped += 1
            continue

        age_seconds = (now - observed_at.astimezone(timezone.utc)).total_seconds()
        if age_seconds > MAX_POSITION_AGE_SECONDS:
            continue
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            skipped += 1
            continue

        positions.append(BusPosition(longitude=longitude, latitude=latitude))

    if skipped:
        logger.warning("Omitiendo %d posiciones de buses inválidas", skipped)
    return positions


def _fetch_bus_positions() -> list[BusPosition]:
    token = _get_access_token()
    try:
        response = requests.get(
            BUSES_URL,
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise BusApiError(f"No se pudieron obtener posiciones de buses de la IM: {exc}") from exc
    return _parse_fresh_bus_positions(payload)


@lru_cache(maxsize=1)
def _projected_graph(graph: DiGraph) -> nx.MultiDiGraph:
    if not graph.graph.get("crs"):
        raise BusApiError("El grafo vial no tiene un CRS definido para ubicar los buses.")
    return ox.project_graph(nx.MultiDiGraph(graph))


def map_bus_positions_to_edges(
    graph: DiGraph,
    positions: Sequence[BusPosition],
) -> tuple[dict[tuple[int, int], int], int]:
    """Assign each fresh bus to its closest edge when it is within 30 meters."""
    if not positions or graph.number_of_edges() == 0:
        return {}, 0

    projected_graph = _projected_graph(graph)
    transformer = Transformer.from_crs(
        "EPSG:4326",
        projected_graph.graph["crs"],
        always_xy=True,
    )
    bus_x, bus_y = transformer.transform(
        [position.longitude for position in positions],
        [position.latitude for position in positions],
    )
    edge_ids, distances = ox.distance.nearest_edges(
        projected_graph,
        X=bus_x,
        Y=bus_y,
        return_dist=True,
    )

    counts: Counter[tuple[int, int]] = Counter()
    matched_positions = 0
    for edge_id, distance in zip(edge_ids, distances, strict=True):
        if float(distance) > MAX_BUS_TO_EDGE_DISTANCE_M:
            continue
        u, v, _key = edge_id
        counts[(u, v)] += 1
        if graph.has_edge(v, u):
            counts[(v, u)] += 1
        matched_positions += 1

    return dict(counts), matched_positions


def fetch_bus_traffic(graph: DiGraph) -> BusTraffic:
    """Fetch and spatially match live bus positions, caching the result for 60 seconds."""
    global _traffic_cache, _traffic_cache_graph_id, _traffic_cache_expires_at

    with _cache_lock:
        now = time.monotonic()
        graph_id = id(graph)
        if (
            _traffic_cache is not None
            and _traffic_cache_graph_id == graph_id
            and now < _traffic_cache_expires_at
        ):
            return _traffic_cache

        positions = _fetch_bus_positions()
        edge_counts, matched_positions = map_bus_positions_to_edges(graph, positions)
        _traffic_cache = BusTraffic(
            edge_counts=edge_counts,
            fresh_positions=len(positions),
            matched_positions=matched_positions,
            fetched_at=datetime.now(timezone.utc),
        )
        _traffic_cache_graph_id = graph_id
        _traffic_cache_expires_at = now + BUS_CACHE_SECONDS
        logger.info(
            "Datos de buses actualizados: %d posiciones vigentes, %d asociadas a calles",
            len(positions),
            matched_positions,
        )
        return _traffic_cache

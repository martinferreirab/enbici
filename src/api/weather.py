"""Open-Meteo API client for fetching current wind data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Wind grid points across Montevideo
WIND_GRID_POINTS = {
    "sw": (-34.9060, -56.2000),    # Rambla Sur / Centro-Oeste
    "se": (-34.9150, -56.1400),    # Pocitos / Rambla Este
    "n": (-34.8550, -56.2000),     # Prado / Centro-Norte
    "nw": (-34.8200, -56.2500),    # Colón / Pasaje
}


@dataclass(frozen=True)
class WindData:
    """Current wind conditions."""
    speed_ms: float  # Wind speed in m/s
    direction_degrees: float  # Wind direction in degrees (0-360, from north clockwise)


@dataclass(frozen=True)
class WindGrid:
    """Wind data at multiple grid points across Montevideo."""
    points: dict[str, WindData]  # Grid point name -> WindData

    def get_wind_at_location(self, lat: float, lon: float) -> WindData | None:
        """Get wind data for nearest grid point to a location."""
        if not self.points:
            return None

        min_distance = float("inf")
        nearest_key = None

        for key, (grid_lat, grid_lon) in WIND_GRID_POINTS.items():
            # Simple Euclidean distance (good enough for small area)
            distance = ((lat - grid_lat) ** 2 + (lon - grid_lon) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                nearest_key = key

        return self.points.get(nearest_key) if nearest_key else None


def fetch_wind_data() -> WindGrid | None:
    """
    Fetch current wind speed and direction for 4 grid points across Montevideo.

    Uses a single batch HTTP request to Open-Meteo API.
    Returns WindGrid with wind data at each point, or None if API call fails.
    """
    try:
        # Build batch request with all 4 grid points
        latitudes = [coords[0] for coords in WIND_GRID_POINTS.values()]
        longitudes = [coords[1] for coords in WIND_GRID_POINTS.values()]

        params = {
            "latitude": ",".join(str(lat) for lat in latitudes),
            "longitude": ",".join(str(lon) for lon in longitudes),
            "current": "wind_speed_10m,wind_direction_10m",
            "timezone": "America/Montevideo",
        }

        response = requests.get(OPEN_METEO_URL, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()

        # API returns a list when querying multiple coordinates
        if not isinstance(data, list):
            data = [data]

        wind_points = {}
        for idx, (key, _coords) in enumerate(WIND_GRID_POINTS.items()):
            if idx < len(data):
                current = data[idx].get("current", {})
                wind_speed_kmh = float(current.get("wind_speed_10m", 0.0))
                wind_direction = float(current.get("wind_direction_10m", 0.0))

                # Convert km/h to m/s
                wind_speed_ms = wind_speed_kmh / 3.6

                wind_points[key] = WindData(
                    speed_ms=wind_speed_ms,
                    direction_degrees=wind_direction,
                )
                logger.info(f"Wind at {key}: {wind_speed_ms:.1f} m/s from {wind_direction:.0f}°")

        return WindGrid(points=wind_points)

    except Exception as e:
        logger.warning(f"Failed to fetch wind data from Open-Meteo: {e}")
        return None

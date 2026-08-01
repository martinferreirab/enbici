"""Open-Meteo API client for fetching current wind data."""

from __future__ import annotations

import logging
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
MONTEVIDEO_LAT = -34.9011
MONTEVIDEO_LON = -56.1645


@dataclass(frozen=True)
class WindData:
    """Current wind conditions."""
    speed_ms: float  # Wind speed in m/s
    direction_degrees: float  # Wind direction in degrees (0-360, from north clockwise)


def fetch_wind_data() -> WindData | None:
    """
    Fetch current wind speed and direction for Montevideo from Open-Meteo.

    Returns None if the API call fails.
    """
    try:
        params = {
            "latitude": MONTEVIDEO_LAT,
            "longitude": MONTEVIDEO_LON,
            "current": "wind_speed_10m,wind_direction_10m",
            "timezone": "America/Montevideo",
        }

        response = requests.get(OPEN_METEO_URL, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        current = data.get("current", {})

        wind_speed = current.get("wind_speed_10m", 0.0)
        wind_direction = current.get("wind_direction_10m", 0.0)

        logger.info(f"Wind data fetched: {wind_speed:.1f} m/s from {wind_direction:.0f}°")

        return WindData(
            speed_ms=float(wind_speed),
            direction_degrees=float(wind_direction),
        )
    except Exception as e:
        logger.warning(f"Failed to fetch wind data from Open-Meteo: {e}")
        return None


def calculate_wind_penalty(
    wind_direction_deg: float,
    edge_bearing_deg: float,
    wind_speed_ms: float,
    wind_weight: float,
) -> float:
    """
    Calculate wind cost penalty for an edge based on wind direction vs edge bearing.

    Returns a multiplier (1.0 = no penalty, > 1.0 = increased cost).

    The penalty increases when wind is headwind (0-90°) and decreases with tailwind (180-270°).
    Formula: 1.0 + (wind_weight / 10) * wind_speed * (1 + cos(angle_to_wind))
    """
    if wind_weight <= 0 or wind_speed_ms <= 0:
        return 1.0

    # Normalize angles to 0-360
    wind_dir = wind_direction_deg % 360
    edge_bearing = edge_bearing_deg % 360

    # Calculate angle between wind direction and edge bearing
    # This is the angle a cyclist would experience relative to their direction of travel
    angle_diff = (wind_dir - edge_bearing) % 360

    # Convert to radians, -180 to 180 range for easier calculation
    if angle_diff > 180:
        angle_diff = angle_diff - 360

    import math

    # cos(angle_diff) = 1 when wind is from behind (headwind), -1 when tailwind
    # We want to penalize headwind, so we use (1 + cos(angle_diff))
    cos_angle = math.cos(math.radians(angle_diff))
    headwind_factor = 1.0 + cos_angle  # Range: 0 (tailwind) to 2 (headwind)

    penalty = 1.0 + (wind_weight / 10.0) * wind_speed_ms * (headwind_factor / 2.0)
    return penalty

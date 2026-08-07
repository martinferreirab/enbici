"""Función de costo para camino mínimo con penalización por pendiente y viento."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.weather import WindData

MAX_GRADE = 0.25


@dataclass(frozen=True)
class WindCostFactor:
    """Wind cost adjustment factors for a route."""
    average_wind_speed_ms: float
    average_headwind_factor: float
    wind_cost_increase_percent: float


def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate compass bearing (0-360°) from point 1 to point 2.

    Returns bearing in degrees where 0° = North, 90° = East, 180° = South, 270° = West.
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    lon_diff = math.radians(lon2 - lon1)

    y = math.sin(lon_diff) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(
        lat2_rad
    ) * math.cos(lon_diff)

    bearing_rad = math.atan2(y, x)
    bearing_deg = (math.degrees(bearing_rad) + 360) % 360

    return bearing_deg


def _calculate_wind_penalty(
    wind_direction_deg: float,
    edge_bearing_deg: float,
    wind_speed_ms: float,
    wind_weight: float,
) -> float:
    """
    Calculate wind cost penalty for an edge.

    Returns a multiplier (1.0 = no penalty, > 1.0 = increased cost).
    Penalizes headwind, rewards tailwind.
    """
    if wind_weight <= 0 or wind_speed_ms <= 0:
        return 1.0

    wind_dir = wind_direction_deg % 360
    edge_bearing = edge_bearing_deg % 360

    # Angle between wind direction and edge bearing
    angle_diff = (wind_dir - edge_bearing) % 360
    if angle_diff > 180:
        angle_diff = angle_diff - 360

    # cos(angle_diff) = 1 for headwind, -1 for tailwind
    cos_angle = math.cos(math.radians(angle_diff))
    headwind_factor = (1.0 + cos_angle) / 2.0  # Normalized to 0-1

    penalty = 1.0 + (wind_weight / 10.0) * wind_speed_ms * headwind_factor
    return penalty


def edge_cost(
    length: float,
    grade: float,
    elevation_weight: float,
    wind_data: WindData | None = None,
    wind_weight: float = 0.0,
    edge_bearing_deg: float | None = None,
    is_park_path: bool = False,
    allow_parks: bool = True,
) -> float:
    """
    Calculate edge cost with elevation, wind penalties, and park path control.

    Fórmula: length * (1 + elevation_weight * grade_penalty) * wind_penalty
    Grade penalty is non-linear: quadratic scaling for grades > 3% to amplify cost of steep sections.

    Args:
        length: Edge length in meters
        grade: Grade as decimal (e.g., 0.05 for 5%)
        elevation_weight: Elevation penalty factor (0-10)
        wind_data: Current wind conditions (speed_ms, direction_degrees)
        wind_weight: Wind penalty factor (0-10)
        edge_bearing_deg: Edge bearing in degrees (0-360), required if wind_data provided
        is_park_path: Whether edge is a park/plaza internal path
        allow_parks: Whether to allow traversing park paths (True) or penalize (False)
    """
    # Penalize or block park paths if not allowed
    if is_park_path and not allow_parks:
        return length * 10.0  # 10x cost penalty for park paths when not allowed

    uphill_grade = min(max(grade, 0.0), MAX_GRADE)

    # Non-linear penalty for steep grades (>3%) to force visible deviations
    if uphill_grade > 0.03:
        steep_portion = uphill_grade - 0.03
        uphill_grade = 0.03 + steep_portion ** 2

    base_cost = length * (1.0 + elevation_weight * uphill_grade)

    if wind_data and wind_weight > 0 and edge_bearing_deg is not None:
        wind_penalty = _calculate_wind_penalty(
            wind_data.direction_degrees,
            edge_bearing_deg,
            wind_data.speed_ms,
            wind_weight,
        )
        return base_cost * wind_penalty

    return base_cost

"""Geocoding utilities for resolving place names to coordinates."""

from __future__ import annotations

import logging
from typing import NamedTuple

from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Create geocoder instance with custom user agent
geocoder = Nominatim(user_agent="enbici_router/1.0")


class Coordinates(NamedTuple):
    """Latitude and longitude pair."""
    lat: float
    lon: float


def geocode_place(place_name: str, city: str = "Montevideo", country: str = "Uruguay") -> Coordinates | None:
    """
    Resolve a place name to coordinates using Nominatim.

    Args:
        place_name: Name of the location (e.g., "Plaza Independencia", "Cerro")
        city: City name (default "Montevideo")
        country: Country name (default "Uruguay")

    Returns:
        Coordinates(lat, lon) if found, None if not found or API fails
    """
    try:
        # Build full address query
        query = f"{place_name}, {city}, {country}"
        logger.debug(f"Geocoding: {query}")

        # Query nominatim
        location = geocoder.geocode(query, language="es")

        if location:
            return Coordinates(lat=location.latitude, lon=location.longitude)
        else:
            logger.warning(f"Place not found: {query}")
            return None

    except Exception as e:
        logger.error(f"Geocoding error for '{place_name}': {str(e)}")
        return None

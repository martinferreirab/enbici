from pydantic import BaseModel, Field


class WindMetrics(BaseModel):
    """Wind conditions affecting the route."""
    wind_speed_ms: float = Field(..., description="Current wind speed in m/s")
    wind_direction_deg: float = Field(..., description="Wind direction in degrees (0-360)")
    average_headwind_factor: float = Field(
        ..., description="Average headwind factor on route (0=tailwind, 1=headwind)"
    )


class RouteResponse(BaseModel):
    """Single optimal route response."""
    distance_km: float = Field(..., description="Route distance in kilometers")
    elevation_gain_m: float = Field(..., description="Elevation gain in meters")
    node_count: int = Field(..., description="Number of nodes in the route")
    wind_metrics: WindMetrics | None = Field(
        None, description="Wind metrics if wind_weight > 0"
    )
    map_url: str = Field(..., description="URL to the generated map HTML file")

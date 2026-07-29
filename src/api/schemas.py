from pydantic import BaseModel, Field


class RouteResponse(BaseModel):
    distance_km: float = Field(..., description="Total route distance in kilometers")
    elevation_gain_m: float = Field(..., description="Total elevation gain in meters")
    node_count: int = Field(..., description="Number of nodes in the route")
    map_url: str = Field(..., description="URL to the generated map HTML file")

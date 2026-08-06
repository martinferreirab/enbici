from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles

from src.api.schemas import RouteResponse, WindMetrics
from src.api.weather import fetch_wind_data
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
from src.utils.geocoding import geocode_place
from src.visualization.map_export import export_route_map

# Global graph instance (loaded once on startup)
G = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global G
    # Startup: load graph once
    G = load_montevideo_graph()
    print("✓ Montevideo graph loaded and cached in memory")
    yield
    # Shutdown (cleanup if needed)
    pass


app = FastAPI(
    title="enbici API",
    description="Bike routing engine for Montevideo with elevation-aware cost function",
    version="2.0",
    lifespan=lifespan,
)

# Mount static files for serving generated maps
app.mount("/static", StaticFiles(directory="output"), name="static")


@app.get("/route", response_model=RouteResponse, tags=["routing"])
async def get_route(
    origin_place: str | None = Query(default=None, description="Origin place name (e.g., 'Plaza Independencia')"),
    origin_lat: float | None = Query(default=None, description="Origin latitude (use origin_place instead if available)"),
    origin_lon: float | None = Query(default=None, description="Origin longitude (use origin_place instead if available)"),
    dest_place: str | None = Query(default=None, description="Destination place name (e.g., 'Cerro de Montevideo')"),
    dest_lat: float | None = Query(default=None, description="Destination latitude (use dest_place instead if available)"),
    dest_lon: float | None = Query(default=None, description="Destination longitude (use dest_place instead if available)"),
    elevation_weight: float = Query(
        default=5.0,
        ge=0,
        le=10,
        description="Elevation weight factor (0-10, default 5.0)",
    ),
    wind_weight: float = Query(
        default=0.0,
        ge=0,
        le=10,
        description="Wind weight factor (0-10, default 0.0, disabled if 0)",
    ),
    bikeway_weight: float = Query(
        default=0.0,
        ge=0,
        le=10,
        description="Bikeway discount factor (0-10, default 0.0, prefers bikeways if > 0)",
    ),
) -> RouteResponse:
    """
    Calculate optimal bike route from origin to destination.

    Accepts either place names (e.g., "Plaza Independencia") or coordinates (lat/lon).
    If both are provided, place names take precedence.

    Returns route metrics and URL to the generated map.
    """
    if G is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    try:
        # Resolve origin coordinates
        if origin_place:
            coords = geocode_place(origin_place)
            if not coords:
                raise HTTPException(
                    status_code=400,
                    detail=f"Origin place not found: '{origin_place}'"
                )
            origin_lat, origin_lon = coords.lat, coords.lon
        elif origin_lat is None or origin_lon is None:
            raise HTTPException(
                status_code=400,
                detail="Provide either origin_place or both origin_lat & origin_lon"
            )

        # Resolve destination coordinates
        if dest_place:
            coords = geocode_place(dest_place)
            if not coords:
                raise HTTPException(
                    status_code=400,
                    detail=f"Destination place not found: '{dest_place}'"
                )
            dest_lat, dest_lon = coords.lat, coords.lon
        elif dest_lat is None or dest_lon is None:
            raise HTTPException(
                status_code=400,
                detail="Provide either dest_place or both dest_lat & dest_lon"
            )

        # Fetch wind data if needed
        wind_data = None
        if wind_weight > 0:
            wind_data = fetch_wind_data()

        # Find nearest nodes to the given coordinates
        origin_node = nearest_node(G, origin_lat, origin_lon)
        dest_node = nearest_node(G, dest_lat, dest_lon)

        if origin_node == dest_node:
            raise HTTPException(
                status_code=400, detail="Origin and destination are the same node"
            )

        # Find route with wind data and bikeway preferences if available
        path = find_route(
            G,
            origin_node,
            dest_node,
            elevation_weight=elevation_weight,
            wind_data=wind_data,
            wind_weight=wind_weight,
            bikeway_weight=bikeway_weight,
        )

        if not path:
            raise HTTPException(status_code=404, detail="No route found")

        # Compute metrics
        metrics = compute_route_metrics(
            G,
            path,
            elevation_weight=elevation_weight,
            wind_data=wind_data,
            wind_weight=wind_weight,
            bikeway_weight=bikeway_weight,
        )

        # Export map
        map_path = "output/ruta_montevideo.html"
        export_route_map(
            G,
            path,
            (origin_lat, origin_lon),
            (dest_lat, dest_lon),
            metrics,
            map_path,
        )

        # Build wind metrics if available
        wind_metrics = None
        if wind_data:
            wind_metrics = WindMetrics(
                wind_speed_ms=wind_data.speed_ms,
                wind_direction_deg=wind_data.direction_degrees,
                average_headwind_factor=metrics.average_headwind_factor,
            )

        return RouteResponse(
            distance_km=metrics.total_distance_m / 1000.0,
            elevation_gain_m=metrics.total_elevation_gain_m,
            node_count=metrics.node_count,
            map_url="/static/ruta_montevideo.html",
            wind_metrics=wind_metrics,
            bikeway_percentage=metrics.bikeway_percentage,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "graph_loaded": G is not None}

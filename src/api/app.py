import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.buses import try_fetch_bus_traffic
from src.api.schemas import Coordinate, RouteResponse, WindMetrics
from src.api.users import router as users_router
from src.api.weather import fetch_wind_data
from src.config import CORS_ORIGINS, IS_PRODUCTION
from src.db.database import init_db
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
from src.routing.query_log import log_route_query
from src.utils.geocoding import geocode_place
from src.visualization.map_export import export_route_map

# Global graph instance (loaded once on startup)
G = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global G
    init_db()
    # Startup: load graph once
    G = load_montevideo_graph()
    print("✓ Montevideo graph loaded and cached in memory")
    yield
    # Shutdown (cleanup if needed)
    pass


app = FastAPI(
    title="enbici API",
    description="Bike routing engine for Montevideo with elevation, wind, and live bus costs",
    version="2.0",
    lifespan=lifespan,
    # Swagger/OpenAPI solo fuera de producción.
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router)

# Mount static files for serving generated maps
app.mount("/static", StaticFiles(directory="output"), name="static")


# `def` (no `async def`): geocoding, APIs externas y Dijkstra bloquean; FastAPI corre los
# endpoints sync en un threadpool, así una ruta lenta no congela /health, /login, etc.
@app.get("/route", response_model=RouteResponse, tags=["routing"])
def get_route(
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
    allow_parks: bool = Query(
        default=True,
        description="Allow traversing park/plaza internal paths (True) or penalize (False)",
    ),
    max_against_traffic_blocks: int = Query(
        default=0,
        ge=0,
        le=3,
        description="Max blocks (segments) to allow cycling against one-way traffic (0-3, 0=disabled)",
    ),
    bus_weight: float = Query(
        default=1.0,
        ge=0,
        le=10,
        description="Live bus penalty factor (0=ignore buses, 1=default 1.15x/1.30x per edge, 2=1.30x/1.60x, ...)",
    ),
    include_map: bool = Query(
        default=False,
        description="Also render a Folium HTML map and return its map_url (debug; the mobile app uses route_coordinates)",
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

        # Fetch wind grid data
        wind_grid = None
        if wind_weight > 0:
            wind_grid = fetch_wind_data()

        # Find nearest nodes
        origin_node = nearest_node(G, origin_lat, origin_lon)
        dest_node = nearest_node(G, dest_lat, dest_lon)

        if origin_node == dest_node:
            raise HTTPException(
                status_code=400, detail="Origin and destination are the same node"
            )

        bus_traffic = try_fetch_bus_traffic(G) if bus_weight > 0 else None
        bus_counts = bus_traffic.edge_counts if bus_traffic else None

        # Find optimal route
        path = find_route(
            G,
            origin_node,
            dest_node,
            elevation_weight=elevation_weight,
            wind_data=wind_grid,
            wind_weight=wind_weight,
            allow_parks=allow_parks,
            max_against_traffic_blocks=max_against_traffic_blocks,
            bus_counts=bus_counts,
            bus_weight=bus_weight,
        )

        if not path:
            raise HTTPException(status_code=404, detail="No route found")

        # Compute metrics
        metrics = compute_route_metrics(
            G,
            path,
            elevation_weight=elevation_weight,
            wind_data=wind_grid,
            wind_weight=wind_weight,
            allow_parks=allow_parks,
            max_against_traffic_blocks=max_against_traffic_blocks,
            bus_counts=bus_counts,
        )
        log_route_query(
            G, path, metrics,
            source="api",
            origin=(origin_lat, origin_lon),
            dest=(dest_lat, dest_lon),
            origin_place=origin_place,
            dest_place=dest_place,
            wind_weight=wind_weight,
            bus_weight=bus_weight,
            allow_parks=allow_parks,
            max_against_traffic_blocks=max_against_traffic_blocks,
            bus_traffic=bus_traffic,
        )

        # Mapa Folium opcional; nombre único para que dos requests simultáneos no se pisen.
        map_url = None
        if include_map:
            map_name = f"ruta_api_{uuid.uuid4().hex[:12]}.html"
            export_route_map(
                G,
                path,
                (origin_lat, origin_lon),
                (dest_lat, dest_lon),
                metrics,
                f"output/{map_name}",
            )
            map_url = f"/static/{map_name}"

        # Build wind metrics
        wind_metrics = None
        if wind_grid and wind_weight > 0:
            first_wind = next(iter(wind_grid.points.values())) if wind_grid.points else None
            if first_wind:
                wind_metrics = WindMetrics(
                    wind_speed_ms=first_wind.speed_ms,
                    wind_direction_deg=first_wind.direction_degrees,
                    average_headwind_factor=metrics.average_headwind_factor,
                )

        return RouteResponse(
            distance_km=metrics.total_distance_m / 1000.0,
            elevation_gain_m=metrics.total_elevation_gain_m,
            node_count=metrics.node_count,
            live_buses_near_route=metrics.live_buses_near_route,
            wind_metrics=wind_metrics,
            map_url=map_url,
            route_coordinates=[
                Coordinate(lat=G.nodes[n]["y"], lon=G.nodes[n]["x"]) for n in path
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "graph_loaded": G is not None}

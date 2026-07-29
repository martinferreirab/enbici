from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles

from src.api.schemas import RouteResponse
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics
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
    origin_lat: float = Query(..., description="Origin latitude"),
    origin_lon: float = Query(..., description="Origin longitude"),
    dest_lat: float = Query(..., description="Destination latitude"),
    dest_lon: float = Query(..., description="Destination longitude"),
    elevation_weight: float = Query(
        default=5.0,
        ge=0,
        le=10,
        description="Elevation weight factor (0-10, default 5.0)",
    ),
) -> RouteResponse:
    """
    Calculate optimal bike route from origin to destination.

    Returns route metrics and URL to the generated map.
    """
    if G is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")

    try:
        # Find nearest nodes to the given coordinates
        origin_node = nearest_node(G, origin_lat, origin_lon)
        dest_node = nearest_node(G, dest_lat, dest_lon)

        if origin_node == dest_node:
            raise HTTPException(
                status_code=400, detail="Origin and destination are the same node"
            )

        # Find route
        path = find_route(G, origin_node, dest_node, elevation_weight=elevation_weight)

        if not path:
            raise HTTPException(status_code=404, detail="No route found")

        # Compute metrics
        metrics = compute_route_metrics(G, path, elevation_weight=elevation_weight)

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

        return RouteResponse(
            distance_km=metrics.total_distance_m / 1000.0,
            elevation_gain_m=metrics.total_elevation_gain_m,
            node_count=metrics.node_count,
            map_url="/static/ruta_montevideo.html",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Routing error: {str(e)}")


@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "graph_loaded": G is not None}

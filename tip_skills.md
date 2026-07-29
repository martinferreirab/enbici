# Instructions & Project Skills for enbici

## 1. Geospatial & Graph Optimization Skill (OSMnx + NetworkX)
- ALWAYS load the cached graph file (`.graphml`) if it exists locally before attempting to query OpenStreetMap via `osmnx`. Downloading OSM data on every run is strictly forbidden.
- When working with `networkx`, ensure graph edge attributes include length (meters) and calculated grade (percentage).
- Remember that `osmnx` graphs are MultiDiGraphs by default. Convert to DiGraph if required by custom routing algorithms, preserving edge attributes.
- Use spatial indexes (`rtree` or built-in `osmnx.distance.nearest_nodes`) for fast nearest-node lookups from lat/lon coordinates.

## 2. Fast Route Cost Function
- When calculating path weights, write vector-friendly or pure-Python lean helper functions to keep A*/Dijkstra evaluations fast.
- Formula baseline: `weight = length * (1 + elevation_weight * max(0, grade))`.
- Keep elevation grade capped at realistic values (e.g., max 0.25 / 25%) to avoid math artifacts from noisy elevation datasets.

## 3. Python 3.12 & Dependency Management
- ALWAYS use `uv` for dependency management (`uv add <package>`, `uv venv`, `uv run`).
- Do NOT use standard `pip` or create virtual environments manually.
- Use explicit type annotations (`type hints`) and Pydantic v2 for API schemas.

## 4. API & Map Export Pattern
- Return clean GeoJSON for route endpoints in FastAPI.
- Keep Folium map generation modular in `/src/visualization.py`. Export maps to temporary or static HTML files for easy previewing.
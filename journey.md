# enbici — Journey Log

> Archivo de memoria del proyecto. Actualizar al final de cada sesión de trabajo.
> Última actualización: **2026-08-10** (Resolución IDW a 100m; caché de grafo migrada a pickle binario)

---

## Qué es enbici

Motor de ruteo para bicicletas en **Montevideo, Uruguay**, sobre el grafo vial de OpenStreetMap. Calcula rutas óptimas con una función de costo que penaliza pendientes ascendentes y viento de frente.

Documentos de referencia del proyecto:
- `source_idea.md` — especificación completa y plan por fases
- `tip_skills.md` — reglas técnicas obligatorias para el agente (caché, fórmulas, uv, etc.)

---

## Estado actual

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 1** — Motor de Grafos y Elevación | ✅ | Grafo cacheado (pickle binario), elevación real (IDW), ruteo Dijkstra, mapa HTML |
| **Fase 2** — API REST (FastAPI) | ✅ | Endpoint `GET /route`, schemas Pydantic, lifespan context |
| **Fase 3** — Ponderación climática (Open-Meteo) | ✅ | `wind_weight`, Wind Grid de 4 puntos, métricas de viento en respuesta |
| **Fase 4** — UI Streamlit | ✅ | Búsqueda por geocoding, mapa Folium en vivo, perfil de elevación (Plotly) |
| **Fase 5** — Ciclovías | ❌ Removida | Implementada y luego eliminada en refactor (2026-08-06); no existe en el código actual |
| **Fase 6** — Geocoding (Búsqueda por Nombre) | ✅ | Nominatim, única forma de ingresar ubicaciones en Streamlit |
| **Elevación real (IDW)** | ✅ | Reemplazó elevación mockeada; ver "Decisiones técnicas clave" |
| **Caché de grafo en pickle** | ✅ | Boot ~0.25s vía `data/montevideo_final.pkl`; elimina corrupción y bloat de aristas |
| **Rutas alternativas / multi-ruta** | ❌ Removida | Se implementó y luego se revirtió a arquitectura de ruta única (2026-08-08) |
| **Against-traffic tolerance** | ✅ | Funcional pero raramente usado (red principal ya es óptima en la mayoría de rutas) |
| **Park paths (parques/plazas)** | ✅ | Incentivo funcional; topología rara vez ofrece shortcuts reales |

---

## Estructura del repo

```
enbici/
├── main.py                          # Script de validación (punto de entrada)
├── run_server.py                    # Punto de entrada para API FastAPI
├── app_streamlit.py                 # UI Streamlit
├── pyproject.toml                   # Dependencias gestionadas con uv
├── source_idea.md                   # Spec del proyecto
├── tip_skills.md                    # Reglas técnicas del agente
├── journey.md                       # Este archivo
├── scripts/
│   ├── enrich_elevation_idw.py      # Enriquecimiento de elevación real (IDW), resumible
│   └── test_elevation_routing.py    # Verifica que elevation_weight afecte el costo/ruteo
├── data/
│   ├── montevideo.graphml           # Fuente XML persistente (elevación/grade real)
│   ├── montevideo_final.pkl         # Caché binaria del DiGraph final (fast path de boot)
│   └── elevation_samples_cache.json # Cache de elevaciones reales por nodo (para IDW resumible)
├── output/
│   └── ruta_*.html                  # Mapas Folium generados
└── src/
    ├── graph/
    │   ├── loader.py                # Carga/caché del grafo (pickle fast path + build path)
    │   └── elevation.py             # Elevación por nodo + grade por arista
    ├── routing/
    │   ├── cost.py                  # Función de costo edge_cost()
    │   └── pathfinder.py            # Dijkstra, nearest_node, RouteMetrics
    ├── utils/
    │   └── geocoding.py             # Geocoding con Nominatim (place name → lat/lon)
    ├── visualization/
    │   └── map_export.py            # Exportación HTML con Folium (ruta única)
    └── api/
        ├── schemas.py                # Pydantic v2 schemas (RouteResponse)
        ├── weather.py                # Open-Meteo wind API client (WindGrid)
        └── app.py                    # FastAPI app, lifespan, endpoints
```

---

## Entorno y ejecución

- **Python**: 3.12+, gestionado exclusivamente con **`uv`** (no pip, no venv manual)
- `pyproject.toml`: `[tool.uv] package = false`
- Imports: `from src.graph.loader import ...`

```bash
uv sync                              # instalar deps

uv run python main.py                # validación motor de grafos → output/ruta_montevideo.html

uv run python run_server.py          # API FastAPI en http://127.0.0.1:8000
#   /docs (Swagger), /health, GET /route?...

uv run streamlit run app_streamlit.py  # UI interactiva en http://localhost:8501

uv run python scripts/enrich_elevation_idw.py   # (re)generar elevación real; ver Decisiones técnicas
uv run python scripts/test_elevation_routing.py # verificar que elevation_weight afecta el ruteo
```

**Ejemplos `GET /route`:**
```bash
# Por coordenadas
curl "http://127.0.0.1:8000/route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0"

# Por nombre de lugar (geocoding) + viento
curl "http://127.0.0.1:8000/route?origin_place=Plaza%20Independencia&dest_place=Cerro%20de%20Montevideo&elevation_weight=5.0&wind_weight=3.0"
```

Respuesta (`RouteResponse`, estructura plana, sin alternativas):
```json
{
  "distance_km": 5.11,
  "elevation_gain_m": 40.6,
  "node_count": 59,
  "map_url": "/static/ruta_montevideo.html",
  "wind_metrics": { "wind_speed_ms": 4.7, "wind_direction_deg": 99.0, "average_headwind_factor": 0.5 }
}
```

**Dependencias clave:** `osmnx`, `networkx`, `fastapi`/`uvicorn`, `pydantic` v2, `folium`, `streamlit`/`streamlit-folium`, `plotly`, `geopy` (geocoding), `scikit-learn` (requerido por osmnx para `nearest_nodes`), `scipy`/`numpy` (IDW).

---

## Decisiones técnicas clave

### Caché del grafo — dos niveles (CRÍTICO)

`load_montevideo_graph()` en `src/graph/loader.py`:
1. **Fast path**: si `data/montevideo_final.pkl` existe → `pickle.load()` y retorna de inmediato (**~0.25s**, sin re-marcado ni conversión).
2. **Build path** (solo si falta el `.pkl`): carga/descarga `data/montevideo.graphml` → enriquece elevación si falta → `_mark_park_paths()` + `_add_against_traffic_edges()` (idempotente, no duplica aristas) → convierte a `DiGraph` → guarda el pickle **atómicamente** (`.pkl.tmp` + `Path.replace()`).
3. **Regla estricta**: nunca re-descargar OSM si el `.graphml` existe.

**⚠️ Importante**: si se regenera `data/montevideo.graphml` directamente (p. ej. re-corriendo `enrich_elevation_idw.py`), hay que **borrar `data/montevideo_final.pkl`** para que el próximo boot reconstruya el pickle con los datos actualizados — si no, el servidor sigue sirviendo el grafo pickled viejo.

- Grafo OSM: `"Montevideo, Uruguay"`, `network_type="bike"` — 23,254 nodos, 70,841 aristas (DiGraph final, incluye against-traffic).

### Elevación — real, vía IDW (no mockeada)

- `scripts/enrich_elevation_idw.py`: enriquecimiento offline con datos reales.
  1. Selecciona ~1,500 nodos muestra: 80% grilla espacial uniforme (celdas de **100m**), 20% puntos críticos (anclas en costa/Rambla y zonas altas, 20 nodos más cercanos a cada ancla).
  2. Fetch real vía Open-Meteo Elevation API (`https://api.open-meteo.com/v1/elevation`, POST, **máx. 100 coordenadas por request** — límite duro del API, no 1000). Rate-limitea (429) después de ~6 batches; el fetch es **resumible**: cada batch exitoso se persiste en `data/elevation_samples_cache.json`, y re-correr el script retoma solo lo pendiente sin perder progreso ni duplicar requests.
  3. Interpolación IDW (`scipy.spatial.cKDTree`, k=8 vecinos, peso=`1/distancia²`) para los ~21,700 nodos restantes.
  4. Recalcula `grade` por arista y guarda `data/montevideo.graphml`.
- Rango actual: **0-79m**. Atributo `elevation` en nodos, `grade` en aristas (acotado a ±25%, `MAX_GRADE=0.25`).
- **Limitación de resolución conocida**: calles paralelas a <100-200m suelen interpolar a elevaciones casi idénticas, por lo que `elevation_weight` alto no siempre produce una ruta visiblemente distinta (el efecto se nota más en `elevation_gain_m` que en el path elegido). No es un bug de ruteo — es un límite de resolución de la malla de muestreo.

### Función de costo (`src/routing/cost.py → edge_cost()`)

```
uphill_grade = clip(grade, 0, MAX_GRADE)
grade_penalty = uphill_grade ** 1.5          # ley de potencia — amplifica pendientes pronunciadas
base_cost = length * (1 + elevation_weight * grade_penalty) * park_multiplier * against_traffic_multiplier
cost = base_cost * wind_penalty              # si hay wind_data
wind_penalty = 1 + (wind_weight/10) * wind_speed * headwind_factor
headwind_factor = (1 + cos(ángulo_viento_rumbo)) / 2   # 0=tailwind, 1=headwind
```

- Solo penaliza pendientes **ascendentes**; downhill no cuesta extra.
- **`grade ** 1.5`** (no cuadrático-con-umbral): una versión anterior usaba `0.03 + (grade-0.03)²`, que al elevar al cuadrado una fracción <1 **reducía** el efecto de pendientes pronunciadas en vez de amplificarlo — bug corregido 2026-08-10.
- `park_multiplier`: 0.5x si `is_park_path` y `allow_parks=True` (incentivo); 10x si `allow_parks=False` (penalización).
- `against_traffic_multiplier`: `inf` si `max_against_traffic_blocks=0`; 6.0x si >0.
- Bearing de arista vía `_calculate_bearing(lat1, lon1, lat2, lon2)`.
- Algoritmo: Dijkstra (`networkx.shortest_path`) con función de peso dinámica.

### RouteMetrics / API

- `RouteResponse` es **plano** (sin rutas alternativas): `distance_km`, `elevation_gain_m`, `node_count`, `map_url`, `wind_metrics` (null si `wind_weight=0`).
- `WindGrid`: 4 puntos (SW Rambla, SE Pocitos, N Prado, NW Colón) fetched en un solo batch; `get_wind_at_location(lat, lon)` asigna el punto más cercano a cada arista.
- Visualización: Folium, marcador verde=origen/rojo=destino, ruta única (sin dashed alternativas), export a `output/*.html`.

---

## Notas para el agente en futuras sesiones

1. **Leer primero**: `journey.md`, `source_idea.md`, `tip_skills.md`
2. **Nunca re-descargar OSM** si `data/montevideo.graphml` existe
3. **Siempre usar `uv`** para deps y ejecución (`uv add`, `uv run`)
4. El grafo retornado por `load_montevideo_graph()` ya es un `DiGraph` listo para ruteo
5. `nearest_nodes(G, lon, lat)` — OSMnx recibe **lon antes que lat**
6. Las coordenadas en nodos OSMnx están en `node["y"]` (lat) y `node["x"]` (lon)
7. La API carga el grafo UNA SOLA VEZ en el contexto `lifespan` de FastAPI; no modificar esto
8. **Park paths**: El atributo `is_park_path` se re-marca en cada load (se guardan en caché pero se actualizan siempre)
9. **Against-traffic edges**: El atributo `is_against_traffic` se agrega en cada load (edges reverse de one-way streets)
10. **Geocoding**: usar `src.utils.geocoding.geocode_place()` para resolver nombres de lugares → coordenadas
11. **API simplificada** (2026-08-08): retorna UNA SOLA ruta óptima con parámetros: `elevation_weight` (0-10), `wind_weight` (0-10), `allow_parks` (boolean), `max_against_traffic_blocks` (0-3)
12. **Wind Grid**: `fetch_wind_data()` retorna `WindGrid` con 4 puntos, usar `get_wind_at_location(lat, lon)` para asignar a edges
13. **Routing**: `find_route()` retorna lista de nodos (single path). `compute_route_metrics()` acepta `WindData | WindGrid | None` y usa lookups por ubicación
14. **Map Export**: `export_route_map()` solo renderiza una ruta (sin alternativas). Parámetros: G, path, origin, destination, metrics, output_path
15. **Streamlit**: Muestra mapa interactivo → métricas → perfil de elevación. Sin tabs, sin alternativas. Simple y enfocado.
16. **Elevations**: Graph now contains **real topography** (0-92m range), IDW-interpolated from 1,510 real Open-Meteo samples via `scripts/enrich_elevation_idw.py` (see "IDW Elevation Enrichment" section, 2026-08-10). No longer mocked. To add more precision, extend the anchor/grid lists in that script and re-run it — it resumes from `data/elevation_samples_cache.json` and only fetches new samples.
17. **Boot time**: ~8.43s due to park path & against-traffic re-marking on every load. No external elevation API calls. Acceptable for production.
18. Actualizar este archivo al cerrar cada sesión con cambios, decisiones y resultados nuevos
19. **Graph cache is now two-tier**: `load_montevideo_graph()` checks `data/montevideo_final.pkl` (binary DiGraph, fast path, ~0.25s) before falling back to `data/montevideo.graphml` (XML, build path, only runs once). If you update the `.graphml` directly (e.g. re-running `enrich_elevation_idw.py`), delete `data/montevideo_final.pkl` afterward or the server will keep serving the stale pickled graph.

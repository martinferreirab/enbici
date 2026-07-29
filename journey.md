# enbici — Journey Log

> Archivo de memoria del proyecto. Actualizar al final de cada sesión de trabajo.
> Última actualización: **2026-07-29** (Fase 2 completada)

---

## Qué es enbici

Motor de ruteo para bicicletas en **Montevideo, Uruguay**, sobre el grafo vial de OpenStreetMap. Calcula rutas óptimas con una función de costo que penaliza pendientes ascendentes (y en el futuro, viento/clima).

Documentos de referencia del proyecto:
- `source_idea.md` — especificación completa y plan por fases
- `tip_skills.md` — reglas técnicas obligatorias para el agente (caché, fórmulas, uv, etc.)

---

## Estado actual

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fase 1** — MVP Motor de Grafos y Elevación | ✅ Completada | Grafo cacheado, elevación, ruteo Dijkstra, mapa HTML |
| **Fase 2** — API REST (FastAPI) | ✅ Completada | Endpoint `GET /route`, schemas Pydantic, lifespan context, static files |
| Fase 3 — Ponderación climática (Open-Meteo) | ⬜ Pendiente | `wind_weight` |
| Fase 4 — UI Streamlit | ⬜ Pendiente | Ajuste interactivo de parámetros |

---

## Estructura del repo

```
enbici/
├── main.py                      # Script de validación Fase 1 (punto de entrada)
├── run_server.py                # Punto de entrada para API Fase 2
├── pyproject.toml               # Dependencias gestionadas con uv
├── source_idea.md               # Spec del proyecto
├── tip_skills.md                # Reglas técnicas del agente
├── journey.md                   # Este archivo
├── data/
│   └── montevideo.graphml       # Caché del grafo (~31 MB, NO re-descargar)
├── output/
│   └── ruta_montevideo.html     # Mapa Folium generado por endpoints
└── src/
    ├── graph/
    │   ├── loader.py            # Descarga/carga/caché del grafo OSM
    │   └── elevation.py         # Elevación por nodo + grade por arista
    ├── routing/
    │   ├── cost.py              # Función de costo edge_cost()
    │   └── pathfinder.py        # Dijkstra, nearest_node, RouteMetrics
    ├── visualization/
    │   └── map_export.py        # Exportación HTML con Folium
    └── api/
        ├── __init__.py          # Módulo API
        ├── schemas.py           # Pydantic v2 schemas (RouteResponse)
        └── app.py               # FastAPI app, lifespan, endpoints
```

---

## Entorno y ejecución

### Instalación de dependencias

```bash
# Instalar deps (solo la primera vez o tras cambios en pyproject.toml)
uv sync
```

- **Python**: 3.12+
- **Gestor de deps**: `uv` exclusivamente (no pip, no venv manual)
- **pyproject.toml**: `[tool.uv] package = false` → app script, no paquete instalable
- **Imports**: Los módulos se importan como `from src.graph.loader import ...`

### Fase 1: Validación del motor de grafos

```bash
# Ejecutar validación y generar mapa de prueba
uv run python main.py
```

Genera `output/ruta_montevideo.html` con la ruta de prueba.

### Fase 2: Servidor API REST

```bash
# Lanzar servidor FastAPI/uvicorn en http://127.0.0.1:8000
uv run python run_server.py
```

**Puntos de acceso:**
- **Interactive API docs**: http://127.0.0.1:8000/docs (Swagger UI)
- **Health check**: `GET /health`
- **Route endpoint**: `GET /route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0`
- **Generated map**: http://127.0.0.1:8000/static/ruta_montevideo.html

**Ejemplos de uso:**

Ruta de prueba (Plaza Independencia → Facultad de Ingeniería):
```bash
curl "http://127.0.0.1:8000/route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0"
```

Respuesta esperada:
```json
{
  "distance_km": 5.11,
  "elevation_gain_m": 84.0,
  "node_count": 59,
  "map_url": "/static/ruta_montevideo.html"
}
```

**Detalles técnicos Fase 2:**

| Componente | Archivo | Descripción |
|------------|---------|-------------|
| Schemas | `src/api/schemas.py` | `RouteResponse` con campos distance_km, elevation_gain_m, node_count, map_url |
| FastAPI app | `src/api/app.py` | App con lifespan context manager que carga el grafo UNA VEZ al iniciar; endpoints `/route` y `/health`; monta `/static` desde `output/` |
| Static files | Configured in `app.py` | Sirve archivos desde `output/` directory para permitir acceso al HTML generado |
| Server entry | `run_server.py` | Lanza uvicorn en `127.0.0.1:8000` |

**Carga del grafo (lifespan):**

El grafo se carga una única vez cuando el servidor inicia (en el contexto `lifespan` de FastAPI). Todas las solicitudes reutilizan la instancia global `G`, evitando rechargues innecesarios.

### Dependencias instaladas

| Paquete | Uso |
|---------|-----|
| `osmnx` | Descarga/carga grafo OSM, nearest_nodes, to_digraph |
| `networkx` | shortest_path (Dijkstra) |
| `geopy` | Distancias geodésicas (mock de elevación) |
| `folium` | Mapas HTML interactivos |
| `requests` | API Open-Elevation |
| `pandas` | Requerido por el stack geoespacial |
| `scikit-learn` | **Requerido por osmnx** para `nearest_nodes` en grafos no proyectados |

---

## Decisiones técnicas clave

### Caché del grafo (CRÍTICO)

- Archivo: `data/montevideo.graphml`
- **Regla estricta** (`tip_skills.md`): si el `.graphml` existe, cargarlo siempre. Nunca re-descargar OSM en cada ejecución.
- Flujo en `load_montevideo_graph()`:
  1. Si existe caché → `ox.load_graphml()`
  2. Si no existe → `ox.graph_from_place("Montevideo, Uruguay", network_type="bike")` → enriquecer → guardar
  3. Si el grafo cacheado no tiene elevación/grade → enriquecer y re-guardar
  4. Convertir a `DiGraph` con `ox.convert.to_digraph(G)` antes de retornar

### Grafo OSM

- Place query: `"Montevideo, Uruguay"`
- Network type: `"bike"`
- Tamaño actual: **23 254 nodos**, **60 689 aristas**
- Tipo interno OSMnx: `MultiDiGraph` → se convierte a `DiGraph` para ruteo

### Elevación

- Fuente primaria: [Open-Elevation API](https://api.open-elevation.com/api/v1/lookup) (POST, lotes de 100 nodos)
- Fallback: mock heurístico basado en distancia al Cerro de Montevideo (`elevation.py → _mock_elevation`)
- Atributo en nodos: `elevation` (metros)
- Atributo en aristas: `grade` = `(elev_v - elev_u) / length`, acotado a ±25 % (`MAX_GRADE = 0.25`)
- Elevación y grade quedan **persistidos en el .graphml** tras la primera ejecución

### Función de costo

```
weight = length * (1 + elevation_weight * max(0, grade))
```

- Implementada en `src/routing/cost.py → edge_cost()`
- Solo penaliza pendientes **ascendentes** (`max(0, grade)`)
- `grade` positivo acotado al 25 % para evitar artefactos de datos ruidosos
- Algoritmo: Dijkstra vía `networkx.shortest_path` con función de peso dinámica

### Métricas de ruta (`RouteMetrics`)

- `total_distance_m`: suma de `length` de aristas
- `total_elevation_gain_m`: suma de `max(0, elev_v - elev_u)` por arista
- `node_count`: cantidad de nodos en el path

### Visualización

- Folium + OpenStreetMap tiles
- Marcadores verde (origen) / rojo (destino)
- Panel flotante con métricas de la ruta principal y comparativa
- Output: `output/ruta_montevideo.html`

---

## Validación Fase 1 (resultados conocidos)

**Ruta de prueba**: Plaza Independencia → Facultad de Ingeniería (UdelaR)

| Coordenada | lat | lon |
|------------|-----|-----|
| Origen (Plaza Independencia) | -34.9060 | -56.1996 |
| Destino (Fac. Ingeniería) | -34.8947 | -56.1520 |

| Métrica | `elevation_weight=0` | `elevation_weight=5` |
|---------|---------------------|----------------------|
| Distancia | 5.11 km | 5.11 km |
| Desnivel + | 87.0 m | 84.0 m |
| Nodos | 60 | 59 |
| Δ vs distancia | — | +1 m dist, −3 m desnivel |

> La diferencia es pequeña porque ese tramo es relativamente llano. Para ver efecto más marcado, probar rutas que crucen el Cerro o la rambla con pendientes pronunciadas.

**Tiempos de ejecución observados:**
- Primera ejecución (descarga OSM + ~23k nodos de elevación API): ~4 min
- Ejecuciones posteriores (solo caché): ~6 s

---

## API pública de módulos (para reutilizar)

```python
from src.graph.loader import load_montevideo_graph
from src.routing.pathfinder import find_route, nearest_node, compute_route_metrics, RouteMetrics
from src.routing.cost import edge_cost
from src.visualization.map_export import export_route_map

G = load_montevideo_graph()
origin = nearest_node(G, lat, lon)
dest = nearest_node(G, lat, lon)
path = find_route(G, origin, dest, elevation_weight=5.0)
metrics = compute_route_metrics(G, path, elevation_weight=5.0)
export_route_map(G, path, (lat_o, lon_o), (lat_d, lon_d), metrics, "output/mapa.html")
```

---

## Pendiente / próximos pasos

### Fase 2 — API REST ✅ COMPLETADA
- [x] Crear `src/api/` con FastAPI + uvicorn
- [x] Endpoint `GET /route` con params: `origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`, `elevation_weight` (0–10)
- [x] Respuesta lightweight: distancia, desnivel, conteo de nodos, URL del mapa (NO GeoJSON de coordenadas)
- [x] Schemas con Pydantic v2
- [x] Lifespan context manager para cargar grafo UNA SOLA VEZ
- [x] Static files mount para servir HTML desde `/static`
- [x] Endpoint `/health` para health checks
- [x] Swagger UI en `/docs`

### Mejoras opcionales (no bloqueantes)
- [ ] Probar rutas con mayor contraste topográfico para validar mejor el peso de elevación
- [ ] Exportar también JSON además del HTML (requerido en spec, aún no implementado)
- [ ] Agregar `.gitignore` para `.venv/`, `data/*.graphml` (archivo grande), `output/`
- [ ] Considerar A* con heurística geodésica como alternativa a Dijkstra puro

---

## Resumen de Fase 2 (2026-07-29)

**Implementación completada:**
- ✅ Módulo `src/api/` con FastAPI + uvicorn
- ✅ `schemas.py`: `RouteResponse` con Pydantic v2 (distance_km, elevation_gain_m, node_count, map_url)
- ✅ `app.py`: FastAPI app con lifespan context manager para cargar grafo UNA VEZ en memoria
- ✅ Endpoint `GET /route` con validación de parámetros (origin_lat/lon, dest_lat/lon, elevation_weight 0-10)
- ✅ Static files mounting (`/static` → `output/`) para servir HTML generados
- ✅ Endpoint `/health` para verificación de estado
- ✅ Respuesta JSON lightweight (sin GeoJSON de coordenadas)
- ✅ Swagger UI en `/docs` para testing interactivo
- ✅ `run_server.py`: script de entrada para lanzar el servidor

**Dependencias agregadas:** fastapi==0.140.13, uvicorn==0.51.0, pydantic==2.13.4

**Cómo probar:**
```bash
# Terminal 1: Lanzar servidor
uv run python run_server.py

# Terminal 2: Hacer solicitud
curl "http://127.0.0.1:8000/route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0"

# O abrir Swagger UI
open http://127.0.0.1:8000/docs
```

---

## Notas para el agente en futuras sesiones

1. **Leer primero**: `journey.md`, `source_idea.md`, `tip_skills.md`
2. **Nunca re-descargar OSM** si `data/montevideo.graphml` existe
3. **Siempre usar `uv`** para deps y ejecución (`uv add`, `uv run`)
4. El grafo retornado por `load_montevideo_graph()` ya es un `DiGraph` listo para ruteo
5. `nearest_nodes(G, lon, lat)` — OSMnx recibe **lon antes que lat**
6. Las coordenadas en nodos OSMnx están en `node["y"]` (lat) y `node["x"]` (lon)
7. La API carga el grafo UNA SOLA VEZ en el contexto `lifespan` de FastAPI; no modificar esto
8. Actualizar este archivo al cerrar cada sesión con cambios, decisiones y resultados nuevos

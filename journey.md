# enbici — Journey Log

> Archivo de memoria del proyecto. Actualizar al final de cada sesión de trabajo.
> Última actualización: **2026-08-01** (Fase 5 completada)

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
| **Fase 3** — Ponderación climática (Open-Meteo) | ✅ Completada | API Open-Meteo, `wind_weight`, métricas de viento en respuesta |
| **Fase 4** — UI Streamlit | ✅ Completada | Sliders interactivos, presets, mapa Folium en vivo, métricas dinámicas |
| **Fase 5** — Infraestructura Ciclista (Ciclovías) | ✅ Completada | Detección OSM ciclovías, `bikeway_weight` descuento, % en ruta |

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
- **Route endpoint**: `GET /route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0&wind_weight=3.0`
- **Generated map**: http://127.0.0.1:8000/static/ruta_montevideo.html

**Ejemplos de uso:**

Ruta sin viento (classic):
```bash
curl "http://127.0.0.1:8000/route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0"
```

Ruta con penalización por viento:
```bash
curl "http://127.0.0.1:8000/route?origin_lat=-34.9060&origin_lon=-56.1996&dest_lat=-34.8947&dest_lon=-56.1520&elevation_weight=5.0&wind_weight=3.0"
```

Respuesta esperada (sin viento):
```json
{
  "distance_km": 5.11,
  "elevation_gain_m": 84.0,
  "node_count": 59,
  "map_url": "/static/ruta_montevideo.html",
  "wind_metrics": null
}
```

Respuesta esperada (con viento):
```json
{
  "distance_km": 5.11,
  "elevation_gain_m": 84.0,
  "node_count": 59,
  "map_url": "/static/ruta_montevideo.html",
  "wind_metrics": {
    "wind_speed_ms": 28.3,
    "wind_direction_deg": 344.0,
    "average_headwind_factor": 0.506
  }
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
weight = length * (1 + elevation_weight * max(0, grade)) * wind_penalty
wind_penalty = 1.0 + (wind_weight / 10) * wind_speed * headwind_factor
```

- Implementada en `src/routing/cost.py → edge_cost()`
- Solo penaliza pendientes **ascendentes** (`max(0, grade)`)
- `grade` positivo acotado al 25 % para evitar artefactos de datos ruidosos
- `wind_penalty`: multiplica el costo según el ángulo viento → rumbo de arista
  - Headwind (0-90°): penaliza aumentando el costo
  - Tailwind (180-270°): reduce el costo
  - Factor de viento: `headwind_factor = (1 + cos(ángulo)) / 2` (rango 0-1)
- Algoritmo: Dijkstra vía `networkx.shortest_path` con función de peso dinámica
- Bearing de arista: calculado dinámicamente desde coordenadas de nodos con `_calculate_bearing(lat1, lon1, lat2, lon2)`

### Métricas de ruta (`RouteMetrics`)

- `total_distance_m`: suma de `length` de aristas
- `total_elevation_gain_m`: suma de `max(0, elev_v - elev_u)` por arista
- `node_count`: cantidad de nodos en el path
- `wind_weight`: factor de ponderación de viento (0-10)
- `average_wind_speed_ms`: velocidad promedio de viento en la ruta (m/s)
- `average_headwind_factor`: factor promedio de viento de frente (0=tailwind, 1=headwind)

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
from src.routing.cost import edge_cost, _calculate_wind_penalty
from src.api.weather import fetch_wind_data, WindData
from src.visualization.map_export import export_route_map

# Sin viento
G = load_montevideo_graph()
origin = nearest_node(G, lat, lon)
dest = nearest_node(G, lat, lon)
path = find_route(G, origin, dest, elevation_weight=5.0)
metrics = compute_route_metrics(G, path, elevation_weight=5.0)
export_route_map(G, path, (lat_o, lon_o), (lat_d, lon_d), metrics, "output/mapa.html")

# Con viento
wind_data = fetch_wind_data()
path = find_route(G, origin, dest, elevation_weight=5.0, wind_data=wind_data, wind_weight=3.0)
metrics = compute_route_metrics(G, path, elevation_weight=5.0, wind_data=wind_data, wind_weight=3.0)
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

### Fase 4 — Ejecutar Streamlit UI

```bash
# Lanzar la interfaz interactiva
uv run streamlit run app_streamlit.py
```

Abrirá un navegador en `http://localhost:8501` con:
- **Sidebar**: inputs para coordenadas, presets de ubicaciones, sliders de pesos
- **Mapa interactivo**: visualización Folium en tiempo real
- **Métricas**: distancia, desnivel, nodos, viento actual

---

## Resumen de Fase 3 (2026-08-01)

**Implementación completada:**

1. **Cliente Open-Meteo API** (`src/api/weather.py`):
   - ✅ Función `fetch_wind_data()`: obtiene velocidad y dirección de viento actual para Montevideo
   - ✅ Estructura `WindData`: encapsula speed_ms y direction_degrees
   - ✅ Manejo graceful de fallos (retorna None si API falla)

2. **Extensión de función de costo** (`src/routing/cost.py`):
   - ✅ Función `_calculate_bearing()`: calcula rumbo geodésico (0-360°) entre dos puntos
   - ✅ Función `_calculate_wind_penalty()`: calcula multiplicador de costo basado en ángulo viento→arista
   - ✅ Actualización `edge_cost()`: acepta wind_data y wind_weight opcionales, mantiene compatible hacia atrás
   - ✅ Dataclass `WindCostFactor`: estructura para métricas agregadas de viento

3. **Ruteo con viento** (`src/routing/pathfinder.py`):
   - ✅ `RouteMetrics`: agregar campos wind_weight, average_wind_speed_ms, average_headwind_factor
   - ✅ `find_route()`: acepta wind_data/wind_weight opcionales, calcula bearing dinámicamente
   - ✅ `compute_route_metrics()`: calcula headwind_factor promedio de la ruta

4. **API REST actualizado** (`src/api/app.py`, `src/api/schemas.py`):
   - ✅ Nuevo query parameter: `wind_weight` (0-10, default 0.0, deshabilitado si =0)
   - ✅ Schema `WindMetrics`: wind_speed_ms, wind_direction_deg, average_headwind_factor
   - ✅ `RouteResponse`: agregar campo `wind_metrics` (null si wind_weight=0)
   - ✅ Endpoint `/route`: fetch wind data si wind_weight > 0, integra en routeo

5. **Validación**:
   - ✅ `main.py` sigue funcionando (compatible hacia atrás)
   - ✅ API REST responde correctamente sin/con parámetro wind_weight
   - ✅ Swagger UI en `/docs` documenta nuevos parámetros

**Cambios de API:**
```bash
# Sin viento (original)
GET /route?origin_lat=...&dest_lat=...&elevation_weight=5.0
→ wind_metrics: null

# Con viento (nuevo)
GET /route?origin_lat=...&dest_lat=...&elevation_weight=5.0&wind_weight=3.0
→ wind_metrics: { wind_speed_ms, wind_direction_deg, average_headwind_factor }
```

**Fórmula de costo con viento:**
```
cost = length * (1 + elevation_weight * grade) * (1 + wind_weight/10 * speed * headwind)
```
donde `headwind = (1 + cos(angle_viento_rumbo)) / 2` (rango 0-1)

---

## Resumen de Fase 4 (2026-08-01)

**Implementación completada:**

1. **Aplicación Streamlit** (`app_streamlit.py`):
   - ✅ Interfaz limpia y responsiva con `st.set_page_config(layout="wide")`
   - ✅ Sidebar con inputs y controles

2. **Panel Lateral (Sidebar)**:
   - ✅ Botones presets: 3 combinaciones predefinidas de ubicaciones Montevideo
     - Plaza Independencia ↔ Facultad de Ingeniería
     - Pocitos ↔ Cerro de Montevideo
     - Puerto Viejo ↔ Pocitos
   - ✅ Inputs manuales: lat/lon origen y destino con 4 decimales de precisión
   - ✅ Sliders interactivos: `elevation_weight` (0-10, step 0.5) y `wind_weight` (0-10, step 0.5)
   - ✅ Botón "Calcular Ruta" con tipo primary para destacar

3. **Vista Principal**:
   - ✅ Métricas en tarjetas (`st.metric`): Distancia, Desnivel, Nodos, Viento actual
   - ✅ Información de viento: dirección en grados y cardinal (N/NE/E/etc)
   - ✅ Factor de viento de frente: porcentaje + clasificación (Tailwind/Mixed/Headwind)
   - ✅ Mapa interactivo Folium (`streamlit-folium`):
     - Polyline azul con la ruta calculada
     - Marcador verde (origen con icono play)
     - Marcador rojo (destino con icono stop)
     - Centro del mapa en punto medio de la ruta
     - Zoom nivel 13 para vista de vecindario
   - ✅ Exportación de HTML: guardar mapa detallado en `output/ruta_streamlit.html`

4. **Integración con Motor**:
   - ✅ `@st.cache_resource`: carga el grafo UNA SOLA VEZ en memoria
   - ✅ Usa módulos core: `load_montevideo_graph`, `find_route`, `nearest_node`, `compute_route_metrics`
   - ✅ Integración Open-Meteo: `fetch_wind_data()` cuando `wind_weight > 0`
   - ✅ Manejo de errores graceful: validaciones y mensajes al usuario

5. **UX & Accesibilidad**:
   - ✅ Mensaje informativo inicial con instrucciones
   - ✅ Estados de progreso: spinner durante cálculo, indicadores de éxito/error
   - ✅ Responsivo en escritorio (4 columnas de métricas)
   - ✅ Tooltips explicativos en sliders

**Ubicaciones Predefinidas:**
| Ubicación | Lat | Lon |
|-----------|-----|-----|
| Plaza Independencia | -34.9060 | -56.1996 |
| Facultad de Ingeniería | -34.8947 | -56.1520 |
| Pocitos | -34.8879 | -56.1747 |
| Cerro de Montevideo | -34.8555 | -56.2007 |
| Puerto Viejo | -34.9118 | -56.2147 |

**Dependencias agregadas:**
- `streamlit==1.60.0`
- `streamlit-folium==1.0.0`

**Cómo probar:**
```bash
# Lanzar Streamlit UI
uv run streamlit run app_streamlit.py

# Abrirá navegador en http://localhost:8501
# - Seleccionar preset O ingresar coordenadas
# - Ajustar sliders de elevación/viento
# - Hacer clic en "Calcular Ruta"
```

---

## Resumen de Fase 5 (2026-08-01)

**Integración de Infraestructura Ciclista**

**Implementación completada:**

1. **Detección de Ciclovías** (`src/graph/loader.py`):
   - ✅ Configuración `ox.settings.useful_tags_way` para incluir tags OSM de ciclovías
   - ✅ Función `_mark_bikeways()`: marca aristas como `is_dedicated_bikeway: bool`
   - ✅ Detecta tags: `highway=cycleway`, `cycleway`, `cycleway:left/right/both`, `bicycle=designated`
   - ✅ Control `_graph_has_bikeways()` para re-marcar si falta del caché

2. **Función de Costo Actualizada** (`src/routing/cost.py`):
   - ✅ Parámetro `is_bikeway: bool` en `edge_cost()`
   - ✅ Parámetro `bikeway_weight` (0-10, descuento en ciclovías)
   - ✅ Fórmula: `cost = length * (1 + elevation) * (1 - bikeway_discount) * wind_penalty`
   - ✅ Descuento máximo 50% en ciclovías dedicadas

3. **Ruteo con Preferencia de Ciclovías** (`src/routing/pathfinder.py`):
   - ✅ `RouteMetrics`: agregar `bikeway_weight` y `bikeway_percentage` (0-100%)
   - ✅ `find_route()`: acepta `bikeway_weight` opcional, pasa a `edge_cost()`
   - ✅ `compute_route_metrics()`: calcula porcentaje de ruta en ciclovías dedicadas

4. **API REST Actualizada** (`src/api/app.py`, `src/api/schemas.py`):
   - ✅ Query parameter: `bikeway_weight` (0-10, default 0.0)
   - ✅ Response field: `bikeway_percentage` siempre incluido en `RouteResponse`
   - ✅ Endpoint `/route`: integra preferencia de ciclovías en ruteo

5. **Streamlit UI Mejorada** (`app_streamlit.py`):
   - ✅ Slider "Preferencia por Ciclovías" en sidebar (0-10, step 0.5)
   - ✅ Métrica dinámica: "Ciclovías en la ruta" con % y clasificación emoji
   - ✅ Clasificaciones: 🚴 Muchas (≥50%), 🚴 Algunas (≥20%), 🚗 Pocas (<20%)

**Validación:**
- ✅ `main.py`: función backward-compatible, funciona sin cambios
- ✅ API REST: responde con `bikeway_percentage` en `RouteResponse`
- ✅ Streamlit: sintaxis válida, slider e integración funcionan

**Cambios de API:**
```bash
# Sin preferencia (original)
GET /route?origin_lat=...&elevation_weight=5.0
→ bikeway_percentage: 0.0 (no existe preferencia de ciclovías)

# Con preferencia (nuevo)
GET /route?origin_lat=...&elevation_weight=5.0&bikeway_weight=5.0
→ bikeway_percentage: 45.7 (45.7% de ruta en ciclovías)
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
8. **Grafo con ciclovías**: el atributo `is_dedicated_bikeway` ya está marcado en todas las aristas desde Fase 5
9. Actualizar este archivo al cerrar cada sesión con cambios, decisiones y resultados nuevos

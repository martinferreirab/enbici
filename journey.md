# enbici — Journey Log

> Archivo de memoria del proyecto. Actualizar al final de cada sesión de trabajo.
> Última actualización: **2026-11-12** (Documentación de costo por tramo y tránsito de ómnibus)

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
| **App móvil — PoC "Client-Side Map-First en React Native"** | ✅ | Port a Android exitoso (APK nativo vía EAS Build, corriendo en dispositivo físico). No requirió modificar el backend. |
| **Live bus traffic** | ✅ | Posiciones recientes asociadas a aristas del grafo y usadas como penalización por tramo |

> **Nota (app móvil):** el código de la app vive en un proyecto separado: `enbici_port_android_beta` (ver su `journey_app_android.md`). Consume `GET /route` tal cual. El backend debe correr **obligatoriamente con `host="0.0.0.0"`** para ser accesible desde el celular.

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
uv run python scripts/test_bus_traffic.py       # tests de costo/matching de ómnibus (sin red)
uv run python consulta_prueba.py                # exporta journey_logs y telemetría a data/*.csv
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
- Rango actual: **0-79m**. Atributo `elevation` en nodos, `grade` en aristas (acotado a ±45%, `MAX_GRADE=0.45`).
- **Limitación de resolución conocida**: calles paralelas a <100-200m suelen interpolar a elevaciones casi idénticas, por lo que `elevation_weight` alto no siempre produce una ruta visiblemente distinta (el efecto se nota más en `elevation_gain_m` que en el path elegido). No es un bug de ruteo — es un límite de resolución de la malla de muestreo.

### Función de costo (`src/routing/cost.py → edge_cost()`)

```
uphill_grade = clip(grade, 0, MAX_GRADE)
elevation_ratio = 1 + elevation_weight * uphill_grade * 1.5
base_cost = length * elevation_ratio * park_multiplier * against_traffic_multiplier
cost = base_cost * wind_penalty * bus_multiplier  # si corresponde
wind_penalty = 1 + (wind_weight/10) * wind_speed * headwind_factor
headwind_factor = (1 + cos(ángulo_viento_rumbo)) / 2   # 0=tailwind, 1=headwind
bus_multiplier = 1 + bus_weight * (base - 1)   # base: 1.0 (0 buses), 1.15 (1-2), 1.30 (3+)
```

- Las pendientes **ascendentes** reciben penalizacion lineal por `elevation_weight`; las bajadas reciben los descuentos individuales descritos a continuacion.
- Las bajadas se descuentan individualmente: menor a 10% cuesta 1.0x; de 10% a 25% inclusive cuesta 0.75x; mayor a 25% cuesta 0.5x. No reciben un recargo por continuidad.
- La penalizacion de elevacion es lineal. Con peso 5, una subida de 5% hace que un tramo cueste 1.375 veces su longitud antes de aplicar los demas factores.
- Si `elevation_ratio > 1.75` en dos aristas consecutivas, desde la segunda se multiplica el costo por `1.10`. Con peso 10, una subida de 5% tiene ratio exactamente 1.75 y no activa la regla; una pendiente mayor sí la supera. Se usa un grafo de estados en Dijkstra para que el costo dependa correctamente de si la arista anterior superó el umbral.
- `park_multiplier`: 0.2x si `is_park_path` y `allow_parks=True` (incentivo); 10x si `allow_parks=False` (penalización).
- `against_traffic_multiplier`: `inf` si `max_against_traffic_blocks=0`; 1.8x si >0. **Limitación actual:** pese al nombre y al selector (0-3), el valor positivo solo habilita las aristas en contramano; no limita el recorrido a esa cantidad de cuadras.
- `bus_multiplier`: se aplica a cada arista según la cantidad de buses asociados a esa arista, escalado por `bus_weight` (0-10, default 1): con peso 1 → 0 buses = 1.0x, 1-2 = 1.15x, 3 o más = 1.30x; con peso 2 → 1.30x/1.60x; con peso 10 → 2.5x/4.0x; con peso 0 no se penaliza **ni se consulta la API**. No se penalizan automáticamente las aristas vecinas ni toda la calle.
- Bearing de arista vía `_calculate_bearing(lat1, lon1, lat2, lon2)`.
- Algoritmo: Dijkstra (`networkx.shortest_path`) con función de peso dinámica.

### Tránsito de ómnibus en tiempo real

- Antes de calcular la ruta se consultan posiciones de ómnibus de la API de transporte público de Montevideo. Solo se consideran posiciones de hasta **300 segundos** de antigüedad.
- La respuesta se cachea por **60 segundos** para el mismo grafo. Cada posición se asigna a la arista más cercana si está a no más de **30 metros**; si existe una arista inversa en el grafo, también se incrementa su conteo.
- El conteo se usa durante la búsqueda de ruta, de modo que puede hacer preferible un desvío si la suma de costos resulta menor. Las posiciones reflejan el momento de la consulta, no predicen dónde estará el ómnibus cuando llegue la persona.
- **Opcional (2026-11-14)**: se usa `try_fetch_bus_traffic()`. Si faltan credenciales, falla la consulta o la respuesta es inválida, se loguea un `WARNING` (`Live bus data unavailable; routing without bus penalty`) y la ruta se calcula igual **sin penalización por buses** (`live_buses_near_route = null`; Streamlit muestra un aviso amarillo). Antes devolvía 503 y dejaba sin ruta a la app. Si la consulta es válida pero no hay posiciones que coincidan con el grafo, el conteo queda vacío (`live_buses_near_route = 0`).
- **Credenciales**: OAuth2 `client_credentials` contra `mvdapi-auth.montevideo.gub.uy` con `MONTEVIDEO_CLIENT_ID` / `MONTEVIDEO_CLIENT_SECRET`. `src/api/buses.py` las lee de `<repo>/.env` con `python-dotenv` (gitignored, permisos 600); las variables exportadas en la shell tienen prioridad. No hace falta `--env-file`.
- Con un fallo de red (no de credenciales) cada request reintenta la autenticación (timeout 10 s), así que el ruteo puede demorar hasta ~10-20 s extra mientras la API de la IM esté caída.
- Los costos son unidades relativas de optimización (la longitud en metros ajustada por multiplicadores), no una medida literal de tiempo, esfuerzo o distancia. Las aristas del grafo no tienen necesariamente 100 m; agruparlas en tramos de 100 m es solo una forma de explicar el cálculo.

Ejemplo **hipotético**, no salida de una ruta real: ocho tramos consecutivos de 100 m, `elevation_weight=10`, viento desactivado, sin parque ni contramano. Se muestra cómo se combinan la pendiente, el recargo por dos subidas consecutivas cuyo ratio supera 1.75, y los buses:

| Tramo | Pendiente | Factor de pendiente | Factor por subida consecutiva | Buses asociados | Factor por buses | Costo |
|------:|----------:|--------------------:|------------------------------:|----------------:|-----------------:|------:|
| 1 | +2% | 1.30 | 1.00 | 0 | 1.00 | 130.00 |
| 2 | +6% | 1.90 | 1.00 | 1 | 1.15 | 218.50 |
| 3 | +8% | 2.20 | 1.10 | 3 | 1.30 | 314.60 |
| 4 | +4% | 1.60 | 1.00 | 0 | 1.00 | 160.00 |
| 5 | +7% | 2.05 | 1.00 | 2 | 1.15 | 235.75 |
| 6 | -5% | 1.00 | 1.00 | 0 | 1.00 | 100.00 |
| 7 | +10% | 2.50 | 1.00 | 2 | 1.15 | 287.50 |
| 8 | +6% | 1.90 | 1.10 | 3 | 1.30 | 271.70 |

Ejemplo de cálculo del tramo 3: `100 m × 2.20 × 1.10 × 1.30 = 314.60`. Los tramos 2 y 3 superan el umbral consecutivamente, así que el recargo adicional comienza en el tramo 3. El tramo 8 también recibe ese recargo porque los tramos 7 y 8 superan el umbral en secuencia.

### RouteMetrics / API

- `RouteResponse` es **plano** (sin rutas alternativas): `distance_km`, `elevation_gain_m`, `node_count`, `map_url`, `wind_metrics` (null si `wind_weight=0`), `route_coordinates`, `live_buses_near_route` (int, o `null` si no hubo datos de ómnibus o `bus_weight=0`).
- `GET /route` acepta `bus_weight` (0-10, default 1.0; >10 → 422).
- **Log de consultas (2026-11-14)**: cada cálculo de ruta (Streamlit `source=streamlit`, API `source=api`) agrega una fila a `data/consultas_rutas.csv` vía `src/routing/query_log.py`: origen/destino, pesos, distancia, datos de ómnibus (frescos en la ciudad, asignados, en la ruta, tramos y metros con bus), multiplicadores y `bus_penalty_extra_m` (metros equivalentes sumados por la penalización). Si falla la escritura solo se loguea; nunca rompe el ruteo.
- `WindGrid`: 4 puntos (SW Rambla, SE Pocitos, N Prado, NW Colón) fetched en un solo batch; `get_wind_at_location(lat, lon)` asigna el punto más cercano a cada arista.
- Visualización: Folium, marcador verde=origen/rojo=destino, ruta única (sin dashed alternativas), export a `output/*.html`.

---

## Usuarios y bitácora de viajes (SQLite + JWT)

- **BD**: SQLite vía SQLAlchemy síncrono (2.x) en `data/enbici.db` (gitignored). `init_db()` (`create_all`) corre en el `lifespan` de `src/api/app.py`, antes de cargar el grafo. No hay framework de migraciones: `_add_missing_journey_columns()` agrega con `ALTER TABLE` las columnas nuevas de `journey_logs` (`is_started`, `is_completed`, `bus_weight`) si faltan.
- **Estructura**: `src/db/` (`database.py` engine/sesión/`get_db`, `models.py`), `src/auth/security.py` (bcrypt, JWT, dependency `get_current_user`), `src/api/users.py` (router, incluido en `app.py`). El ruteo no se tocó.
- **Tablas**:
  - `users`: `id`, `username` (único, se guarda en minúsculas), `password_hash` (bcrypt).
  - `journey_logs`: `id`, `user_id` (FK), `origin_place`, `dest_place`, `distance_km`, `elevation_gain_m`, **y las preferencias con que se calculó la ruta**: `elevation_weight`, `wind_weight`, `bus_weight`, `allow_parks`, `max_against_traffic_blocks`, más `timestamp` (UTC). `bus_weight` (2026-11-14) es opcional en `POST /users/me/routes` (default 1.0, igual que `/route`); las filas anteriores a la migración quedaron en `0` porque se calcularon sin penalización por buses. Guardar los filtros permite reproducir el viaje o analizar qué preferencias usa la gente.
- **Endpoints** (JSON):
  - `POST /register` `{username (3-50), password (6-72)}` → 201 `{access_token, token_type, username}`; 409 si el usuario existe.
  - `POST /login` mismo body → `{access_token, ...}`; 401 si credenciales inválidas.
  - `POST /users/me/routes` (Bearer) body = campos de `journey_logs` sin id/user/timestamp → 201 con el registro.
  - `GET /users/me/routes` (Bearer) → lista del usuario, más reciente primero.
  - `GET /route` sigue siendo público/anónimo.
- **JWT**: HS256, PyJWT, expira a los 30 días, `sub` = id de usuario (string). Secreto: env `ENBICI_JWT_SECRET`, o se autogenera en `data/.jwt_secret` (gitignored; si se borra, se invalidan todas las sesiones).
- **Gotcha deps**: `passlib 1.7.4` es incompatible con `bcrypt>=5`; está pineado `bcrypt==4.0.1`. Instalado con `uv add sqlalchemy passlib "bcrypt==4.0.1" pyjwt`.
- **Tracking de viaje (2026-11-08)**:
  - `journey_logs` suma `is_started` e `is_completed` (bool, default `False`).
  - Nueva tabla `journey_telemetry`: `id`, `journey_id` (FK → `journey_logs.id`), `lat`, `lon`, `timestamp` (UTC, default now), `speed_ms` (nullable).
  - Endpoints (Bearer, `{journey_id}` en el path; 404 si el viaje no existe o es de otro usuario):
    - `POST /users/me/routes/{journey_id}/start` → `is_started = True`, devuelve el viaje.
    - `POST /users/me/routes/{journey_id}/telemetry` body `{lat, lon, speed_ms?}` → 201, inserta en `journey_telemetry`.
    - `POST /users/me/routes/{journey_id}/finish` → `is_completed = True`, devuelve el viaje.
  - `JourneyOut` ahora incluye `is_started`/`is_completed`.
  - **Migración**: `init_db()` agrega con `ALTER TABLE` las dos columnas nuevas si el `.db` es anterior (la tabla de telemetría la crea `create_all`). No hace falta borrar la BD.
  - `GET /route` devuelve además `route_coordinates: [{lat, lon}, ...]` (nodos de la ruta) para dibujar con mapas nativos; `map_url` (Folium) sigue igual para Streamlit.
  - Streamlit: botón "▶️ Simular Inicio de Ruta" (visible tras guardar el viaje) → `/start` + thread daemon que postea a `/telemetry` cada 15 s la Plaza Independencia (-34.9060, -56.1996); botón para detener. El thread no toca `st.session_state` (usa un `threading.Event`).
- Pendiente: HTTPS en producción (hoy el token viaja por http en LAN), rate limiting de login, endpoint para borrar viajes.

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
11. **API simplificada** (2026-08-08): retorna UNA SOLA ruta óptima con parámetros: `elevation_weight` (0-10), `wind_weight` (0-10), `allow_parks` (boolean), `max_against_traffic_blocks` (0-3; actualmente valor positivo habilita contramano, pero no impone un máximo real de cuadras)
12. **Wind Grid**: `fetch_wind_data()` retorna `WindGrid` con 4 puntos, usar `get_wind_at_location(lat, lon)` para asignar a edges
13. **Routing**: `find_route()` retorna lista de nodos (single path). `compute_route_metrics()` acepta `WindData | WindGrid | None` y usa lookups por ubicación
14. **Map Export**: `export_route_map()` solo renderiza una ruta (sin alternativas). Parámetros: G, path, origin, destination, metrics, output_path
15. **Streamlit**: Muestra mapa interactivo → métricas → perfil de elevación. Sin tabs, sin alternativas. Simple y enfocado.
16. **Elevations**: Graph now contains **real topography** (0-92m range), IDW-interpolated from 1,510 real Open-Meteo samples via `scripts/enrich_elevation_idw.py` (see "IDW Elevation Enrichment" section, 2026-08-10). No longer mocked. To add more precision, extend the anchor/grid lists in that script and re-run it — it resumes from `data/elevation_samples_cache.json` and only fetches new samples.
17. **Boot time**: ~8.43s due to park path & against-traffic re-marking on every load. No external elevation API calls. Acceptable for production.
18. Actualizar este archivo al cerrar cada sesión con cambios, decisiones y resultados nuevos
19. **Graph cache is now two-tier**: `load_montevideo_graph()` checks `data/montevideo_final.pkl` (binary DiGraph, fast path, ~0.25s) before falling back to `data/montevideo.graphml` (XML, build path, only runs once). If you update the `.graphml` directly (e.g. re-running `enrich_elevation_idw.py`), delete `data/montevideo_final.pkl` afterward or the server will keep serving the stale pickled graph.
20. **Live buses**: `fetch_bus_traffic()` returns per-edge counts for fresh positions; entry points (API/Streamlit) must call `try_fetch_bus_traffic()` so a bus API failure never blocks routing. Routing applies `1 + bus_weight*(0.15|0.30)` only to edges with matched buses; keep the freshness, cache, and 30m matching rules documented above in sync with `src/api/buses.py`.
21. **Grades se recalculan si cambia `MAX_GRADE`**: el pickle guarda `graph["grade_max"]`; si no coincide con `MAX_GRADE` (hoy 0.45), `load_montevideo_graph()` recalcula `grade` desde las elevaciones de los nodos y re-guarda el pickle. Cualquier nodo virtual que se agregue al grafo **debe tener una elevación realista** (los supernodos de parque usan la media de su componente), o el recálculo genera pendientes falsas.

---

## Sesión 2026-11-08 — Tracking GPS en tiempo real (resumen para el próximo agente)

**Estado**: funcionando de punta a punta (probado en un Android real: ruta en mapa nativo, `/start`, telemetría cada ~15 s en `journey_telemetry`, mock de Streamlit). Detalle de tablas/endpoints en la sección "Tracking de viaje (2026-11-08)" de arriba.

### Qué se hizo
- Backend: flags `is_started`/`is_completed`, tabla `journey_telemetry`, endpoints `start`/`telemetry`/`finish`, `route_coordinates` en `GET /route`, migración automática con `ALTER TABLE` en `init_db()` (`src/db/database.py`).
- Streamlit: "Simular Inicio de Ruta" (thread daemon, Plaza Independencia cada 15 s, botón de stop).
- `consulta_prueba.py` ahora también vuelca la telemetría a `data/telemetria_viajes.csv` (además de `historial_viajes.csv`).
- App móvil (ver `enbici_port_android_beta/journey_app_android.md`): mapa nativo + tracking.

### Gotchas / errores encontrados
1. **Los endpoints de viaje exigen `journey_id`**: hay que guardar la ruta (`POST /users/me/routes`) antes de iniciarla. La app lo hace sola al presionar "Iniciar Ruta" (pide login si hace falta).
2. **Verificación parcial en la sesión**: los tests de los endpoints se hicieron llamando a las funciones directo sobre una copia del `.db`; `starlette.testclient` pide `httpx2`, que no se instaló. Si se quiere test HTTP real: agregar `httpx2` como dep de dev.
3. **El thread de Streamlit no puede tocar `st.session_state`** (no hay script-run context); usa un `threading.Event` guardado en session_state para detenerlo. Cambiar de ruta detiene la simulación.
4. **Telemetría con celular quieto**: `speed_ms` ronda 0–1 m/s por ruido de GPS; no interpretar como movimiento.
5. `data/*.csv` y `output/*.html` son generados; se re-escriben al correr `consulta_prueba.py` / el servidor.
6. El cliente móvil vive en `enbici_port_android_beta/` **dentro de este repo** (rama `martin`), no en un repo aparte. Ver `enbici_port_android_beta/journey_app_android.md`.

### Pendiente / ideas
- Rate limiting, HTTPS, borrar viajes (ya estaban pendientes).
- Endpoint para leer la telemetría de un viaje (hoy solo se ve vía SQL / `consulta_prueba.py`).
- Chequeo de llegada solo cada 15 s en la app; no hay tracking en background.
- Tests HTTP automatizados de los endpoints de viaje.

### Decisiones de cierre (2026-11-08)
- El cliente móvil pasó a ser una carpeta de este repo (`enbici_port_android_beta/`, rama `martin`); ya no hay repo aparte ni snapshot duplicado.
- La API key de Google Maps no se versiona (placeholder en `app.json`, valor vía `GOOGLE_MAPS_API_KEY` en EAS env + `app.config.js`). Detalle y pasos en `enbici_port_android_beta/journey_app_android.md`.
- Fix del crash de arranque en Android (R8 vs `androidx.work` traído por `react-native-maps`): R8 desactivado en `expo-build-properties`. Detalle en la bitácora de la app.
- Tareas pendientes de configuración fuera del código: restringir la key en Google Cloud (package + SHA-1, solo Maps SDK for Android) y cargarla en EAS antes del próximo build.

---

## Sesión 2026-11-14 — Merge de `costo_con_buses_20261113` (costos de pendiente + ómnibus IMM)

**Estado**: integrado en `martin` y `main`. Probado: `scripts/test_bus_traffic.py`, `scripts/test_elevation_routing.py`, imports de todos los módulos, `GET /route` contra la API real de la IM (≈470-490 ómnibus frescos, ≈470 asignados a ≈840 aristas), migración de `bus_weight` sobre copia del `.db`. Respaldo previo al merge: rama local `martin-backup-premerge`.

### Qué se hizo
- Merge del commit `5be3dff` (compañero): `src/api/buses.py`, nuevas funciones de costo (`elevation_cost_ratio` lineal, `downhill_cost_multiplier`, `bus_traffic_multiplier`, recargo por subidas consecutivas con grafo de estados), `MAX_GRADE` 0.25 → 0.45, recálculo de pendientes con `grade_max`.
- Conflictos resueltos: `cost.py` (se tomó la versión nueva de costos, se mantuvo `park_multiplier` 0.2), `app.py` (imports de buses + usuarios/DB), `journey.md`, pickle (se mantuvo el nuestro con supernodos), `.md:Zone.Identifier` (basura de Windows, eliminada).
- Agregado sobre el merge: buses opcionales (`try_fetch_bus_traffic`), `bus_weight` (API, Streamlit, `journey_logs`), `.env` + `python-dotenv`, `pyproj` explícito, log `data/consultas_rutas.csv`, `consulta_prueba.py` con columnas explícitas + multiplicadores, `use_container_width` → `width="stretch"`.

### Errores / hallazgos
1. **Pendientes de contramano con signo invertido** (bug previo): `_add_against_traffic_edges` copiaba `grade` de la arista original → 10.135 aristas a contramano tenían subidas como bajadas. Lo corrige el recálculo de pendientes del compañero.
2. **Supernodos de parque con `elevation=0.0`**: combinado con el recálculo, iba a generar pendientes de hasta ±45% en las 720 aristas de parque (los parques están a ~21 m). Fix: elevación = media del componente (código + pickle existente). Quedan 3 aristas >10% de 0.3-10 m, despreciables.
3. **`/route` devolvía 503 sin credenciales IMM** → app Android y Streamlit sin ruta. Ahora es opcional.
4. **`consulta_prueba.py` exportaba `password_hash`** al CSV (y `id` duplicado) por el `SELECT *`. Corregido; ojo que versiones viejas de `data/historial_viajes.csv` con hashes **siguen en el historial de git**.
5. `pyproj` se usaba directo pero solo llegaba transitivamente (vía geopandas/osmnx).

### Gotchas
- Al cargar el primer pickle sin `grade_max` el server tarda un poco más (recalcula y re-guarda `data/montevideo_final.pkl`).
- `data/consultas_rutas.csv` crece sin límite (una fila por cálculo); no rota.
- Penalizar buses puede cambiar la ruta en cualquier dirección (al encarecer la ruta A, la B puede pasar a ser óptima aunque sea más corta).

### Pendiente
- Rotar el secreto de la IMM (se compartió en un chat) y actualizar `.env`.
- Slider de `bus_weight` en la app Android.
- Decidir si `data/consultas_rutas.csv` se versiona o va a `.gitignore`.
- Persistir `live_buses_near_route` en `journey_logs` si se quiere analizar viajes guardados.

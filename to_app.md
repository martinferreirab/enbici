# enbici_app — Especificación de Port a React Native / Expo

> Documento de especificación definitivo para portar el motor de ruteo `enbici` a una app móvil (`enbici_app`) con React Native + Expo. Consume el backend FastAPI existente (`GET /route`) sin modificarlo.

---

## 1. Overview & Architecture

- **Target**: app minimalista, *Map-First*, para Android/iOS.
- **Stack**: Expo SDK 51+, React Native con **TypeScript**.
- **Concepto central**: un mapa Folium interactivo a pantalla completa, embebido en un `react-native-webview`, superpuesto con:
  - una **barra de búsqueda flotante** en la parte superior (origen/destino + acceso a filtros), y
  - un **bottom sheet deslizable** con las métricas de la ruta calculada.
- El backend (`enbici`, FastAPI) no se modifica — la app es un cliente puro de `GET /route`. El mapa que se muestra es el HTML Folium que el backend ya genera (`map_url`), no un mapa nativo renderizado en la app.

### Dependencias (setup inicial)

```bash
npx create-expo-app enbici_app --template expo-template-blank-typescript
cd enbici_app
npx expo install react-native-webview react-native-gesture-handler react-native-reanimated
```

---

## 2. Complete API Specification

### Base URL

| Entorno | Base URL |
|---|---|
| Emulador/dispositivo físico en la misma LAN que el backend (WSL) | `http://172.30.108.170:8000` |
| Web / desarrollo local (mismo host) | `http://localhost:8000` |

La IP de WSL (`172.30.108.170`) puede cambiar entre reinicios de Windows/WSL — verificar con `wsl hostname -I` antes de cada sesión de desarrollo si la app no conecta. Configurar en `src/config.ts` (sección 5).

### Endpoint: `GET /route`

**Query Parameters:**

| Parámetro | Tipo | Requerido | Default | Descripción |
|---|---|---|---|---|
| `origin_place` | string | opcional* | — | Nombre de lugar, ej. `"Plaza Independencia"` (geocoded server-side vía Nominatim) |
| `dest_place` | string | opcional* | — | Nombre de lugar, ej. `"Pocitos"` |
| `origin_lat` / `origin_lon` | float | opcional* | — | Coordenadas de origen (alternativa a `origin_place`) |
| `dest_lat` / `dest_lon` | float | opcional* | — | Coordenadas de destino (alternativa a `dest_place`) |
| `elevation_weight` | float | no | `5.0` | 0.0–10.0. Penaliza pendientes ascendentes (ley de potencia `grade**1.5`) |
| `wind_weight` | float | no | `0.0` | 0.0–10.0. Penaliza viento de frente. Si es `0`, `wind_metrics` en la respuesta es `null` |
| `allow_parks` | boolean | no | `true` | Si `false`, penaliza fuertemente atravesar parques/plazas |
| `max_against_traffic_blocks` | int | no | `0` | `0`, `1`, `2` o `3`. Tolerancia a ir en contramano en calles de un sentido |

\* Se debe proveer **o bien** `origin_place` **o bien** (`origin_lat` y `origin_lon`) — mismo criterio para destino. El backend devuelve `400 Bad Request` si falta ambos, o si el `place` no se puede geocodificar.

**Ejemplo de request:**

```
GET http://172.30.108.170:8000/route?origin_place=Plaza%20Independencia&dest_place=Pocitos&elevation_weight=5.0&wind_weight=3.0&allow_parks=true&max_against_traffic_blocks=0
```

### Response JSON Schema

```json
{
  "distance_km": 5.11,
  "elevation_gain_m": 84.0,
  "node_count": 59,
  "map_url": "/static/ruta_montevideo.html",
  "wind_metrics": {
    "wind_speed_ms": 4.7,
    "wind_direction_deg": 99.0,
    "average_headwind_factor": 0.258
  }
}
```

| Campo | Tipo | Notas |
|---|---|---|
| `distance_km` | float | Distancia total de la ruta |
| `elevation_gain_m` | float | Desnivel acumulado ascendente |
| `node_count` | int | Cantidad de nodos en el path (no se usa en UI, informativo) |
| `map_url` | string | **Ruta relativa** al backend (ej. `/static/ruta_montevideo.html`) — debe resolverse contra `API_BASE_URL`, nunca usarse tal cual en un `<WebView source={{ uri: ... }}>` |
| `wind_metrics` | object \| `null` | `null` si `wind_weight=0`. Si está presente: `wind_speed_ms` (float), `wind_direction_deg` (float, 0-360), `average_headwind_factor` (float, 0-1; 0=viento a favor, 1=viento en contra) |

**Errores esperados:**
- `400 Bad Request` — lugar no geocodificable, o falta origen/destino.
- `500 Internal Server Error` — sin ruta posible entre los puntos dados (grafo desconectado).

---

## 3. Known Compatibility Traps & Critical Implementation Rules

### CORS & Networking

- El backend FastAPI (`src/api/app.py`) ya tiene configurado:
  ```python
  app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
  ```
  No requiere cambios adicionales para consumo desde la app — **no modificar `src/api/app.py`** como parte de este port.
- `map_url` en la respuesta es **siempre relativo** (ej. `/static/ruta_montevideo.html`). `src/services/api.ts` debe exponer una función `resolveMapUrl(map_url: string): string` que lo concatene con `API_BASE_URL`:
  ```ts
  export function resolveMapUrl(mapUrl: string): string {
    return `${API_BASE_URL}${mapUrl}`;
    // → "http://172.30.108.170:8000/static/ruta_montevideo.html"
  }
  ```
  Nunca pasar `map_url` sin resolver a `WebView`.

### Expo & React Native Web Compatibility

- **No usar props de shadow deprecadas** (`shadowColor`, `shadowOffset`, `shadowOpacity`, `shadowRadius` sueltas en RN Web generan warnings/inconsistencias). Usar `boxShadow` (string CSS, soportado en RN Web y RN ≥0.74) o `elevation` (Android) según plataforma:
  ```ts
  const cardStyle = Platform.select({
    web: { boxShadow: "0px 2px 8px rgba(0,0,0,0.15)" },
    android: { elevation: 4 },
    ios: { shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.15, shadowRadius: 8 },
  });
  ```
- **`pointerEvents` sobre el `WebView`**: los componentes flotantes (barra de búsqueda, bottom sheet) se posicionan con `position: "absolute"` encima del `WebView`. El contenedor raíz de cada overlay debe tener `pointerEvents="box-none"` para que los toques pasen al mapa donde no hay controles interactivos, y los inputs/botones dentro deben tener `pointerEvents="auto"` explícito para seguir siendo tocables.
- **`react-native-webview`** es la única vía soportada para renderizar el mapa Folium (HTML generado por el backend) — no reimplementar el mapa con una librería de mapas nativa; el mapa YA es HTML/Leaflet servido por `enbici`.
- Instalar y configurar `react-native-gesture-handler` y `react-native-reanimated` (requeridos por el bottom sheet deslizable) siguiendo las instrucciones de Expo (`babel.config.js` plugin para reanimated, import de gesture-handler en el entrypoint).

---

## 4. UI/UX Layout Breakdown

### Screen 1: Map View (Background)

- `react-native-webview` a pantalla completa (`StyleSheet.absoluteFill`).
- Carga `resolveMapUrl(map_url)` cuando hay una ruta calculada.
- Estado idle (sin ruta aún): cargar un mapa por defecto — puede ser el último `output/ruta_montevideo.html` servido por el backend, o una página local mínima con el tile de Montevideo centrado, hasta que el usuario calcule la primera ruta.

### Component 2: Floating Top Search Bar

- Tarjeta flotante superpuesta (esquinas redondeadas, `boxShadow`/`elevation`), anclada al top con `SafeAreaView`.
- Input de **origen** (texto libre, geocodificado por nombre vía `origin_place`).
- Input de **destino** (idem, `dest_place`).
- Botón de acción que abre el **Filter Modal** (ícono de settings/sliders).
- Botón/acción para calcular ruta (puede ser un botón "Buscar" en la barra o disparar el cálculo al confirmar ambos campos).

### Component 3: Filter / Settings Modal

- Modal (o bottom sheet secundario) con:
  - Slider `elevation_weight` — rango 0 a 10, paso sugerido 0.5.
  - Slider `wind_weight` — rango 0 a 10, paso sugerido 0.5.
  - Toggle/Switch `allow_parks` (boolean, default `true`).
  - Selector segmentado (0 / 1 / 2 / 3 bloques) para `max_against_traffic_blocks`.
- Botón "Aplicar" que cierra el modal y, si ya hay origen/destino cargados, recalcula la ruta con los nuevos parámetros.

### Component 4: Bottom Sheet / Summary Card

Visible solo cuando hay una ruta calculada (respuesta exitosa de `/route`). Contenido:

| Métrica | Fuente | Cálculo / formato |
|---|---|---|
| Distancia total | `distance_km` | mostrar en km, 2 decimales |
| Tiempo estimado | `distance_km` | `(distance_km / 15) * 60` minutos (velocidad promedio asumida: 15 km/h) |
| Desnivel acumulado | `elevation_gain_m` | mostrar en metros |
| Viento | `wind_metrics` | si no es `null`: velocidad en **m/s y km/h** (`speed_ms * 3.6`), más dirección cardinal derivada de `wind_direction_deg` (N/NE/E/SE/S/SO/O/NO); si es `null`, ocultar esta fila |
| CTA principal | — | botón "**Iniciar Ruta**" (acción a definir en integración con navegación turn-by-turn futura; por ahora puede ser un placeholder/no-op) |

Debe ser deslizable (arrastrable hacia abajo para minimizar, hacia arriba para expandir) usando `react-native-reanimated` + `react-native-gesture-handler`.

---

## 5. Project Structure for `enbici_app`

```
enbici_app/
├── App.tsx
├── babel.config.js                  # plugin de react-native-reanimated
├── src/
│   ├── config.ts                    # API_BASE_URL (por entorno)
│   ├── services/
│   │   └── api.ts                   # fetchRoute(), resolveMapUrl(), manejo de errores
│   ├── components/
│   │   ├── MapViewer.tsx            # wrapper de WebView (carga map_url resuelto)
│   │   ├── TopSearchBar.tsx         # inputs origen/destino + botón de filtros
│   │   ├── FilterModal.tsx         # sliders/toggle/selector de parámetros de ruteo
│   │   └── BottomSheet.tsx         # tarjeta de métricas deslizable + CTA
│   └── types/
│       └── route.ts                 # tipos TS: RouteRequestParams, RouteResponse, WindMetrics
```

### `src/config.ts`

```ts
import { Platform } from "react-native";

export const API_BASE_URL =
  Platform.OS === "web" ? "http://localhost:8000" : "http://172.30.108.170:8000";
```

### `src/services/api.ts`

Responsabilidades:
- `fetchRoute(params: RouteRequestParams): Promise<RouteResponse>` — construye el query string desde `params`, hace `fetch(`${API_BASE_URL}/route?...`)`, valida `response.ok`, parsea JSON, lanza un error tipado con el mensaje del backend en caso de `400`/`500`.
- `resolveMapUrl(mapUrl: string): string` — ver sección 3.
- Manejo de errores de red (backend no accesible, timeout) diferenciado de errores de negocio (400/500 del backend), para que la UI pueda mostrar mensajes distintos ("no se encontró el lugar" vs. "no se pudo conectar al servidor").

### `src/components/MapViewer.tsx`

- Envuelve `WebView` de `react-native-webview`.
- Prop `mapUrl: string | null` — si es `null`, muestra estado idle/placeholder; si no, `source={{ uri: resolveMapUrl(mapUrl) }}`.
- `style={StyleSheet.absoluteFill}`.

### `src/components/TopSearchBar.tsx`, `FilterModal.tsx`, `BottomSheet.tsx`

- Componentes controlados (props + callbacks, sin estado de red propio) — el estado de la ruta calculada y los parámetros de filtro viven en `App.tsx` o un store simple (`useState`/`useReducer`), y se pasan hacia abajo. Mantiene los componentes reutilizables y fáciles de testear.

---

## Notas operativas

- Este documento describe **solo el frontend móvil**. No requiere ni implica cambios en el backend `enbici` (FastAPI) — cualquier discrepancia entre esta spec y el comportamiento real de `GET /route` debe resolverse verificando `src/api/app.py` y `src/api/schemas.py` en el repo `enbici`, no modificando el backend para ajustarse a la app.
- Ver `journey.md` (repo `enbici`) para el estado actual del backend, decisiones de la función de costo, y limitaciones conocidas (p. ej. resolución de la malla de elevación) que pueden explicar por qué `elevation_weight` no siempre produce una ruta visiblemente distinta.

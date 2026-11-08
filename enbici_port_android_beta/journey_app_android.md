# journey_app_android — Bitácora de enbici_port_android_beta

## Sesión 2026-10-25 — Port inicial

### Decisiones arquitectónicas
- Proyecto nuevo e independiente (`/home/martinferreirab/proyectos/enbici_port_android_beta`), Expo SDK 58 + TypeScript. **No toca** el backend FastAPI ni Streamlit de `../enbici`: la app es cliente puro de `GET /route` (spec: `../enbici/to_app.md`).
- Map-First: `react-native-webview` a pantalla completa muestra el HTML Folium del backend (`map_url`, relativo, se resuelve contra la IP base y lleva `?t=` anti-caché).
- Overlays (barra superior, bottom sheet) con `pointerEvents="box-none"` en contenedores y `"auto"` en las tarjetas, para que el mapa siga interactivo.
- Bottom sheet propio con Reanimated 4 + Gesture Handler 3 (`usePanGesture` + `GestureDetector`, API v3, no `Gesture.Pan()`). Colapsa a 90px de "peek".
- Sin Expo Go: build nativo vía EAS (`eas.json`, perfil `preview` → APK). `expo-build-properties` activa `usesCleartextTraffic` porque el backend es `http://` (sin eso Android bloquea fetch y WebView).
- Reanimated 4: el plugin de worklets lo aplica `babel-preset-expo`; no hace falta `babel.config.js`.

### IP de WSL (importante)
- La IP de WSL cambia entre reinicios. `src/config.ts` guarda la URL base en AsyncStorage (clave `enbici:api_base_url`); default `http://172.30.108.170:8000`.
- Se cambia en vivo: **mantener presionado el título "enbici"** (barra superior) → modal `IpConfigModal`. Acepta `IP`, `IP:puerto` o URL completa (normaliza a `http://IP:8000`). Obtener IP: `wsl hostname -I`.
- `fetchRoute(baseUrl, params)` y `resolveMapUrl(baseUrl, mapUrl)` reciben la base como argumento; el estado vive en `App.tsx`. No volver a hardcodear la IP.
- El backend debe escuchar en `0.0.0.0:8000` y el teléfono estar en la misma LAN; WSL2 puede requerir port-forwarding de Windows (`netsh interface portproxy`) para que el teléfono alcance la IP de WSL.

### Problema de Red en WSL2 y Solución Portproxy
**Problema:** el backend corre en WSL2, que tiene su propia IP virtual (`wsl hostname -I`, ej. `172.x.x.x`) no alcanzable desde la LAN. El celular solo ve la IP de Windows en el adaptador WiFi, por lo que no puede conectar directo al servidor FastAPI.

**Solución (PowerShell de Windows como Administrador):**
1. Obtener la IP de WSL: `wsl hostname -I`
2. Reenviar el puerto 8000 de Windows hacia WSL:
```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<IP_WSL>
```
3. Abrir el firewall de Windows:
```powershell
New-NetFirewallRule -DisplayName "FastAPI WSL" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
```
4. Backend corriendo con `host="0.0.0.0"` (`run_server.py`) en WSL.
5. En la app: **mantener presionado el título "enbici"** → ingresar la **IP de Windows (adaptador WiFi, ej. `192.168.x.x`)**, **NO** la de WSL. (`ipconfig` en Windows para verla.)

**Notas:**
- La IP de WSL cambia al reiniciar WSL/Windows: hay que borrar y recrear la regla (`netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0`, luego el `add`). Ver reglas: `netsh interface portproxy show v4tov4`.
- Celular y PC deben estar en la misma red WiFi.

### Login y guardado de rutas (lazy login)
- La app es **anónima por defecto** (Map-First): buscar rutas no requiere cuenta. El login solo se pide al presionar **"Guardar Ruta"** en el BottomSheet.
- Flujo: `saveCurrentRoute()` (`App.tsx`) → `getValidToken()`; si no hay token o está vencido (se lee `exp` del JWT) → abre `AuthModal` (login/registro). Al autenticar, guarda el token y reintenta el guardado automáticamente. Si el backend responde 401 al guardar, se borra el token y se vuelve a pedir login.
- **Token en `expo-secure-store`** (`src/services/tokenStorage.ts`, clave `enbici_jwt`), NO en AsyncStorage (AsyncStorage se sigue usando solo para la URL del backend). Instalado con `npx expo install expo-secure-store`; requiere rebuild del APK (módulo nativo).
- Payload de `POST /users/me/routes`: origen, destino, `distance_km`, `elevation_gain_m` **y los filtros con que se calculó la ruta** (`elevation_weight`, `wind_weight`, `allow_parks`, `max_against_traffic_blocks`). Se toman de `routeQuery` (estado capturado al buscar), no de los inputs actuales, que el usuario pudo editar después.
- `src/services/api.ts`: helper `request()` agrega `Authorization: Bearer <token>`; expone `login`, `register`, `saveRoute`, `listRoutes`.
- UI en `src/components/auth/` (`AuthForm`, `AuthModal`). Endpoints documentados en `../enbici/journey.md`.
- Pendiente: pantalla de historial (`listRoutes` ya existe), logout, usar HTTPS.

### Estado actual
- UI: barra flotante (origen/destino/buscar/filtros), FilterModal (elevación, viento, parques, contramano), BottomSheet (distancia, tiempo a 15 km/h, desnivel, viento m/s + km/h + cardinal, CTA "Iniciar Ruta" no-op), mapa idle Leaflet/OSM centrado en Montevideo (requiere internet).
- API: integrada con `GET /route` (errores de red vs. backend diferenciados, timeout 90s). **Probado en dispositivo físico Android** (APK nativo vía EAS Build) con portproxy de Windows.

### Para un futuro agente
1. Leer este archivo y `../enbici/to_app.md` (spec de la API). No modificar `../enbici`.
2. Estructura: `App.tsx` (estado), `src/config.ts` (IP persistente), `src/services/api.ts`, `src/components/*`, `src/types/route.ts`.
3. Instalar paquetes con `npx expo install`. Verificar con `npx tsc --noEmit`.
4. Build: `npx eas-cli login` → `npx eas-cli build -p android --profile preview` → escanear QR e instalar APK. Primera vez: EAS pedirá crear el proyecto (`eas init`) y generar keystore.
5. Si la app no conecta: revisar IP (long-press título), backend corriendo (`run_server.py`), cleartext habilitado, portproxy de Windows.
6. Pendiente: íconos propios, navegación turn-by-turn ("Iniciar Ruta"), mapa idle offline.

## Sesión 2026-11-08 — Mapa nativo y tracking GPS

### Cambios
- **WebView eliminado**: `npm uninstall react-native-webview`. `MapViewer.tsx` ahora es un `<MapView>` de `react-native-maps` (pantalla completa, mismo lugar en el árbol; los overlays `pointerEvents="box-none"` de `App.tsx` no cambiaron). `map_url` / `resolveMapUrl` ya no se usan en la app (el backend lo sigue devolviendo para Streamlit).
- **Instalado** con `npx expo install react-native-maps expo-location` (react-native-maps 1.29.11, expo-location ~58.0.20). Plugins en `app.json`: `expo-location` (texto del permiso) y `react-native-maps` con `androidGoogleMapsApiKey`.
- **Google Maps API key**: en Android react-native-maps usa Google Maps; en builds EAS sin key el mapa sale en blanco. Reemplazar `YOUR_GOOGLE_MAPS_API_KEY` en `app.json` (Maps SDK for Android habilitado, restringida al package `com.martinferreirab.enbici.beta` + SHA-1 del keystore de EAS). Requiere rebuild nativo (`eas build -p android --profile preview`).
- La ruta se dibuja con `<Polyline>` desde `route_coordinates` (+ marcadores origen/destino) y la cámara hace `fitToCoordinates` al llegar una ruta nueva.

### Flujo de navegación GPS
1. "Iniciar Ruta" (`App.startRoute`): guarda el viaje si aún no lo está (necesita login; si no hay sesión abre `AuthModal` y retoma el inicio al autenticar), pide permiso de ubicación en primer plano (`LocationPermissionError` si lo deniegan) y llama `POST /users/me/routes/{id}/start`.
2. `useJourneyTracking` (`src/hooks/`) usa `Location.watchPositionAsync` (`timeInterval` 15 s, precisión alta) y por cada fix envía `POST .../telemetry` `{lat, lon, speed_ms}` (best-effort, errores ignorados).
3. Mapa: `showsUserLocation` activo y `animateCamera({center, heading: 0, pitch: 0, zoom: 17})` en cada fix → **Norte arriba fijo**; `rotateEnabled`/`pitchEnabled` desactivados mientras se trackea.
4. **Cierre automático**: con cada fix se calcula Haversine (`src/utils/geo.ts`) al último punto de `route_coordinates`; si < **20 m** se quita la suscripción, se llama `POST .../finish` y se muestra la alerta "Llegaste a destino".
5. El botón pasa a "Detener Ruta" (cancela el watch sin llamar `/finish`). Una nueva búsqueda también detiene el tracking.

### Notas
- El chequeo de llegada ocurre solo cada 15 s (cada fix); a ~5 m/s la bici puede pasar a >20 m entre fixes. Si molesta, bajar `timeInterval` o agregar `distanceInterval`.
- Tracking solo en primer plano (sin permiso/servicio de background).
- Verificado: `npx tsc --noEmit` y `npx expo export --platform android` OK. No probado en dispositivo.

### Crash al abrir (APK preview) — R8 vs WorkManager
- `react-native-maps` 1.29.11 agrega `androidx.work:work-runtime`. En el build preview, R8 recortó la clase Room generada de `WorkDatabase` y la app moría en el arranque (`InitializationProvider` → "Failed to create an instance of class androidx.work.impl.WorkDatabase").
- Fix: `expo-build-properties` con `enableMinifyInReleaseBuilds: false` y `enableShrinkResourcesInReleaseBuilds: false` (APK más grande). Alternativa si se quiere R8: `extraProguardRules` con keep de `androidx.work.impl.WorkDatabase_Impl`. Requiere rebuild nativo.

## Resumen de sesión 2026-11-08 — para el agente que continúe

**Estado**: probado en Android real (APK `preview` de EAS): mapa Google nativo, ruta con Polyline, tracking GPS con telemetría al backend. Todo funciona.

### Errores que aparecieron (en orden) y su causa
1. **Crash al abrir** (`InitializationProvider` → "Failed to create an instance of class androidx.work.impl.WorkDatabase"): `react-native-maps` trae `androidx.work`; R8 recortaba la clase Room generada en el build release. Fix: `enableMinifyInReleaseBuilds: false` y `enableShrinkResourcesInReleaseBuilds: false` en `expo-build-properties` (`app.json`).
2. **Mapa negro** + logcat `Google Android Maps SDK: Authorization failure`: el APK se había construido con el placeholder `YOUR_GOOGLE_MAPS_API_KEY`. Fix: key real en `plugins → react-native-maps → androidGoogleMapsApiKey`. Requiere Maps SDK for Android habilitado + facturación activa; si la key se restringe, usar package `com.martinferreirab.enbici.beta` y el SHA-1 del keystore de EAS (`eas credentials`).
3. Cualquier cambio en `app.json` plugins o dependencias nativas ⇒ **rebuild** (`npx eas-cli@latest build -p android --profile preview`); un reload de Metro no alcanza.

### Cómo depurar en Windows (PowerShell, sin `&&`)
```powershell
.\adb logcat -c
.\adb shell am start -n com.martinferreirab.enbici.beta/.MainActivity
.\adb logcat -d > logcat.txt
Select-String -Path logcat.txt -Pattern "FATAL EXCEPTION|Google Android Maps SDK" -Context 2,30
```
Buscar siempre el `Caused by:`. El `adb` vive en `platform-tools`; correr con `.\adb`.

### Archivos clave de esta sesión
`src/components/MapViewer.tsx` (MapView/Polyline/cámara norte-arriba), `src/hooks/useJourneyTracking.ts` (permiso, `/start`, watch 15 s, telemetría, Haversine <20 m → `/finish`), `src/utils/geo.ts`, `src/services/api.ts` (`startJourney`/`sendTelemetry`/`finishJourney`), `App.tsx` (`startRoute`, `savedJourneyId`, `startAfterAuth`), `BottomSheet.tsx` (Iniciar/Detener Ruta).

### Gotchas
- La API key **no debe subirse a git**: está en texto plano en `app.json`. Si se publica el repo, pasar a `app.config.js` + EAS Secrets y restringir la key.
- Esta carpeta es un repo git propio; el repo `enbici` guarda un snapshot en `enbici/enbici_port_android_beta/` (sin key, con placeholder).
- `react-native-webview` ya no está instalado; `map_url` del backend es solo para Streamlit.
- Si se prueba el cierre automático a 20 m en dispositivo, usar un destino cercano a donde se está.
- Pendiente: probar la llegada real (<20 m → alerta "Llegaste a destino"), tracking en background, test de pantalla con ruta muy larga (`fitToCoordinates` usa padding fijo).

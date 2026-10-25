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

#Read `to_app.md` and `journey.md` from `\\wsl.localhost\Ubuntu\home\martinferreirab\proyectos\enbici` if accessible, or follow these updated specifications.

Goal:
Build a minimalist Map-First Android mobile app using React Native & Expo in this directory (`/home/martinferreirab/proyectos/enbici_app`), consuming our FastAPI backend (`GET /route`).

Dependencies Setup:
First, install required mapping, UI, and webview libraries:
- `npx expo install react-native-webview react-native-gesture-handler react-native-reanimated`

Backend API Endpoint Specs (`GET http://172.30.108.170:8000/route`):
Query Parameters:
- `origin_place` (string, optional)
- `dest_place` (string, optional)
- `origin_lat` / `origin_lon` (float, optional)
- `dest_lat` / `dest_lon` (float, optional)
- `elevation_weight` (float: 0.0 to 10.0, default 5.0)
- `wind_weight` (float: 0.0 to 10.0, default 0.0)
- `allow_parks` (boolean, default true)
- `max_against_traffic_blocks` (int: 0, 1, 2, 3, default 0)

Key UI/UX Requirements:
1. Map-First Layout:
   - Full-bleed map display using `react-native-webview` loading `http://172.30.108.170:8000${data.map_url}` when a route is computed (or a default map state when idle).
2. Floating Top Bar:
   - Overlaid card on top of the map with rounded corners and subtle shadow.
   - Origin input field (with quick action for current GPS location if available or default text).
   - Destination input field (geocoded by name via backend).
   - Filter/Settings Modal for route weights:
     * Elevation weight slider (0.0 - 10.0)
     * Wind weight slider (0.0 - 10.0)
     * Allow parks checkbox (boolean)
     * Against-traffic tolerance selector (0, 1, 2, 3 blocks)
3. Slidable Bottom Sheet / Summary Card:
   - When route is computed, display:
     * Total distance (`distance_km`)
     * Estimated time (calculated at 15 km/h: `(distance_km / 15) * 60` mins)
     * Elevation gain (`elevation_gain_m`)
     * Wind metrics (`wind_speed_ms` and `average_headwind_factor` if present)
   - Primary Action Button: "Iniciar Ruta".

Networking & Config:
- Dedicated API service in `src/services/api.js`.
- Base URL configurable in `src/config.js` defaulting to `http://172.30.108.170:8000`.

Keep code modular, clean, and structured for Expo SDK 51+.
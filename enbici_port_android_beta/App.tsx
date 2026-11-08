import { StatusBar } from "expo-status-bar";
import { useEffect, useRef, useState } from "react";
import { Alert, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AuthModal } from "./src/components/auth/AuthModal";
import { BottomSheet } from "./src/components/BottomSheet";
import { FilterModal } from "./src/components/FilterModal";
import { IpConfigModal } from "./src/components/IpConfigModal";
import { MapViewer } from "./src/components/MapViewer";
import { TopSearchBar } from "./src/components/TopSearchBar";
import { DEFAULT_API_BASE_URL, getApiBaseUrl, setApiBaseUrl } from "./src/config";
import { BackendError, fetchRoute, saveRoute } from "./src/services/api";
import { LocationPermissionError, useJourneyTracking } from "./src/hooks/useJourneyTracking";
import { clearToken, getValidToken } from "./src/services/tokenStorage";
import { DEFAULT_FILTERS, JourneyPayload, RouteFilters, RouteResponse } from "./src/types/route";

export default function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [origin, setOrigin] = useState("");
  const [dest, setDest] = useState("");
  const [filters, setFilters] = useState<RouteFilters>(DEFAULT_FILTERS);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [savedJourneyId, setSavedJourneyId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showIp, setShowIp] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [saving, setSaving] = useState(false);
  // Query + filters that produced `route` (the inputs may be edited afterwards).
  const [routeQuery, setRouteQuery] = useState<Pick<JourneyPayload, "origin_place" | "dest_place"> & RouteFilters | null>(null);

  const tracking = useJourneyTracking(baseUrl);
  const startAfterAuth = useRef(false); // "Iniciar Ruta" pressed while logged out

  useEffect(() => { getApiBaseUrl().then(setBaseUrl); }, []);

  async function search(f: RouteFilters = filters, url: string = baseUrl) {
    if (!origin.trim() || !dest.trim()) {
      Alert.alert("Faltan datos", "Ingresá origen y destino.");
      return;
    }
    setLoading(true);
    tracking.stop();
    try {
      const res = await fetchRoute(url, { origin_place: origin.trim(), dest_place: dest.trim(), ...f });
      setRoute(res);
      setRouteQuery({ origin_place: origin.trim(), dest_place: dest.trim(), ...f });
      setSavedJourneyId(null);
    } catch (e) {
      const msg = (e as Error).message;
      Alert.alert(e instanceof BackendError ? "No se pudo calcular la ruta" : "Sin conexión", msg);
    } finally {
      setLoading(false);
    }
  }

  /** Lazy login: the app is anonymous until the user tries to save a route. Returns the journey id, or null. */
  async function saveCurrentRoute(silent = false): Promise<number | null> {
    if (!route || !routeQuery) return null;
    if (savedJourneyId) {
      if (!silent) Alert.alert("Ruta guardada", "Esta ruta ya está en tu historial.");
      return savedJourneyId;
    }
    const token = await getValidToken();
    if (!token) {
      setShowAuth(true);
      return null;
    }
    setSaving(true);
    try {
      const saved = await saveRoute(baseUrl, token, {
        ...routeQuery,
        distance_km: route.distance_km,
        elevation_gain_m: route.elevation_gain_m,
      });
      setSavedJourneyId(saved.id);
      if (!silent) Alert.alert("Ruta guardada", "Quedó en tu historial.");
      return saved.id;
    } catch (e) {
      if (e instanceof BackendError && e.status === 401) {
        await clearToken(); // rejected by the server (expired/revoked)
        setShowAuth(true);
      } else {
        Alert.alert("No se pudo guardar", (e as Error).message);
      }
      return null;
    } finally {
      setSaving(false);
    }
  }

  /** Saves the route if needed, asks for GPS permission, calls /start and begins tracking. */
  async function startRoute() {
    const coords = route?.route_coordinates;
    if (!coords?.length) return;
    startAfterAuth.current = true;
    const id = await saveCurrentRoute(true);
    const token = await getValidToken();
    if (id === null || !token) return; // auth modal is showing; onAuthenticated resumes
    startAfterAuth.current = false;
    try {
      await tracking.start(id, token, coords[coords.length - 1], () => Alert.alert("Llegaste a destino", "¡Buen viaje terminado!"));
    } catch (e) {
      const title = e instanceof LocationPermissionError ? "Permiso denegado" : "No se pudo iniciar la ruta";
      Alert.alert(title, (e as Error).message);
    }
  }

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaProvider>
        <MapViewer coordinates={route?.route_coordinates ?? []} tracking={tracking.active} position={tracking.position} />
        <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
          <TopSearchBar
            origin={origin} dest={dest} loading={loading}
            onOrigin={setOrigin} onDest={setDest}
            onSearch={() => search()}
            onFilters={() => setShowFilters(true)}
            onTitleLongPress={() => setShowIp(true)}
          />
          {route && (
            <BottomSheet
              route={route} saving={saving} tracking={tracking.active}
              onSave={() => saveCurrentRoute()}
              onStart={startRoute} onStop={tracking.stop}
            />
          )}
        </View>
        <FilterModal
          visible={showFilters} filters={filters} onClose={() => setShowFilters(false)}
          onApply={(f) => {
            setFilters(f);
            setShowFilters(false);
            if (origin.trim() && dest.trim() && route) search(f);
          }}
        />
        <IpConfigModal
          visible={showIp} current={baseUrl} onClose={() => setShowIp(false)}
          onSave={async (v) => { setBaseUrl(await setApiBaseUrl(v)); setShowIp(false); }}
        />
        <AuthModal
          visible={showAuth} baseUrl={baseUrl} onClose={() => { startAfterAuth.current = false; setShowAuth(false); }}
          onAuthenticated={() => { setShowAuth(false); startAfterAuth.current ? startRoute() : saveCurrentRoute(); }}
        />
        <StatusBar style="dark" />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });

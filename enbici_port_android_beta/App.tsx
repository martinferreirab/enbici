import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { Alert, StyleSheet, View } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { BottomSheet } from "./src/components/BottomSheet";
import { FilterModal } from "./src/components/FilterModal";
import { IpConfigModal } from "./src/components/IpConfigModal";
import { MapViewer } from "./src/components/MapViewer";
import { TopSearchBar } from "./src/components/TopSearchBar";
import { DEFAULT_API_BASE_URL, getApiBaseUrl, setApiBaseUrl } from "./src/config";
import { BackendError, fetchRoute, resolveMapUrl } from "./src/services/api";
import { DEFAULT_FILTERS, RouteFilters, RouteResponse } from "./src/types/route";

export default function App() {
  const [baseUrl, setBaseUrl] = useState(DEFAULT_API_BASE_URL);
  const [origin, setOrigin] = useState("");
  const [dest, setDest] = useState("");
  const [filters, setFilters] = useState<RouteFilters>(DEFAULT_FILTERS);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [mapUri, setMapUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showIp, setShowIp] = useState(false);

  useEffect(() => { getApiBaseUrl().then(setBaseUrl); }, []);

  async function search(f: RouteFilters = filters, url: string = baseUrl) {
    if (!origin.trim() || !dest.trim()) {
      Alert.alert("Faltan datos", "Ingresá origen y destino.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetchRoute(url, { origin_place: origin.trim(), dest_place: dest.trim(), ...f });
      setRoute(res);
      setMapUri(resolveMapUrl(url, res.map_url));
    } catch (e) {
      const msg = (e as Error).message;
      Alert.alert(e instanceof BackendError ? "No se pudo calcular la ruta" : "Sin conexión", msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <GestureHandlerRootView style={styles.root}>
      <SafeAreaProvider>
        <MapViewer uri={mapUri} />
        <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
          <TopSearchBar
            origin={origin} dest={dest} loading={loading}
            onOrigin={setOrigin} onDest={setDest}
            onSearch={() => search()}
            onFilters={() => setShowFilters(true)}
            onTitleLongPress={() => setShowIp(true)}
          />
          {route && <BottomSheet route={route} />}
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
        <StatusBar style="dark" />
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({ root: { flex: 1 } });

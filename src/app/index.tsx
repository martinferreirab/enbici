import * as Location from 'expo-location';
import { useState } from 'react';
import { Platform, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { WebView } from 'react-native-webview';

import { FilterModal, RouteFilters } from '@/components/filter-modal';
import { RouteSummarySheet } from '@/components/route-summary-sheet';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { TopBar } from '@/components/top-bar';
import { Spacing } from '@/constants/theme';
import { getRoute, resolveMapUrl, RouteResponse } from '@/services/api';

const DEFAULT_FILTERS: RouteFilters = {
  elevationWeight: 5.0,
  windWeight: 0.0,
  allowParks: true,
  maxAgainstTrafficBlocks: 0,
};

export default function MapScreen() {
  const [originText, setOriginText] = useState('');
  const [destText, setDestText] = useState('');
  const [originCoords, setOriginCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [filters, setFilters] = useState<RouteFilters>(DEFAULT_FILTERS);
  const [filtersVisible, setFiltersVisible] = useState(false);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleUseCurrentLocation() {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== 'granted') {
      setError('Permiso de ubicación denegado');
      return;
    }
    const position = await Location.getCurrentPositionAsync({});
    setOriginCoords({ lat: position.coords.latitude, lon: position.coords.longitude });
    setOriginText('Mi ubicación actual');
  }

  async function handleSubmit() {
    if (!originText && !originCoords) {
      setError('Ingresá un origen');
      return;
    }
    if (!destText) {
      setError('Ingresá un destino');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const useOriginCoords = originCoords && originText === 'Mi ubicación actual';
      const result = await getRoute({
        originPlace: useOriginCoords ? undefined : originText,
        originLat: useOriginCoords ? originCoords.lat : undefined,
        originLon: useOriginCoords ? originCoords.lon : undefined,
        destPlace: destText,
        elevationWeight: filters.elevationWeight,
        windWeight: filters.windWeight,
        allowParks: filters.allowParks,
        maxAgainstTrafficBlocks: filters.maxAgainstTrafficBlocks,
      });
      setRoute(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo calcular la ruta');
    } finally {
      setLoading(false);
    }
  }

  function handleStartRoute() {
    // Turn-by-turn navigation is not implemented yet; the map already shows the computed route.
  }

  return (
    <ThemedView style={styles.container}>
      {route ? (
        <WebView source={{ uri: resolveMapUrl(route.map_url) }} style={StyleSheet.absoluteFill} />
      ) : (
        <ThemedView type="backgroundElement" style={StyleSheet.absoluteFill}>
          <ThemedView style={styles.idleState}>
            <ThemedText type="subtitle" style={styles.idleTitle}>
              enbici
            </ThemedText>
            <ThemedText themeColor="textSecondary" style={styles.idleText}>
              Ingresá un origen y un destino para calcular tu ruta en bici.
            </ThemedText>
          </ThemedView>
        </ThemedView>
      )}

      <SafeAreaView style={styles.overlay} pointerEvents="box-none">
        <ThemedView style={styles.topBarWrapper}>
          <TopBar
            originText={originText}
            destText={destText}
            onOriginChange={setOriginText}
            onDestChange={setDestText}
            onUseCurrentLocation={handleUseCurrentLocation}
            onOpenFilters={() => setFiltersVisible(true)}
            onSubmit={handleSubmit}
            loading={loading}
          />
          {error && (
            <ThemedText type="small" themeColor="textSecondary" style={styles.errorText}>
              {error}
            </ThemedText>
          )}
        </ThemedView>

        {route && (
          <RouteSummarySheet route={route} onStartRoute={handleStartRoute} />
        )}
      </SafeAreaView>

      <FilterModal
        visible={filtersVisible}
        filters={filters}
        onChange={setFilters}
        onClose={() => setFiltersVisible(false)}
      />
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  overlay: {
    flex: 1,
    justifyContent: 'space-between',
    backgroundColor: 'transparent',
  },
  topBarWrapper: {
    marginHorizontal: Spacing.three,
    marginTop: Platform.select({ android: Spacing.three, default: 0 }),
    backgroundColor: 'transparent',
  },
  errorText: {
    marginTop: Spacing.one,
    textAlign: 'center',
  },
  idleState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.two,
    paddingHorizontal: Spacing.five,
    backgroundColor: 'transparent',
  },
  idleTitle: {
    textAlign: 'center',
  },
  idleText: {
    textAlign: 'center',
  },
});

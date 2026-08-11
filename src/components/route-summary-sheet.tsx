import { Platform, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { RouteResponse } from '@/services/api';

type RouteSummarySheetProps = {
  route: RouteResponse;
  onStartRoute: () => void;
};

const CARDINAL_DIRECTIONS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'] as const;

function toCardinal(degrees: number): string {
  const index = Math.round(degrees / 45) % 8;
  return CARDINAL_DIRECTIONS[index];
}

export function RouteSummarySheet({ route, onStartRoute }: RouteSummarySheetProps) {
  const theme = useTheme();
  const estimatedMinutes = (route.distance_km / 15) * 60;
  const wind = route.wind_metrics;

  return (
    <ThemedView type="background" style={styles.sheet}>
      <View style={styles.metricsRow}>
        <Metric label="Distancia" value={`${route.distance_km.toFixed(1)} km`} />
        <Metric label="Tiempo est." value={`${Math.round(estimatedMinutes)} min`} />
        <Metric label="Desnivel" value={`${Math.round(route.elevation_gain_m)} m`} />
      </View>

      {wind && (
        <View style={styles.metricsRow}>
          <Metric
            label="Viento"
            value={`${(wind.wind_speed_ms * 3.6).toFixed(1)} km/h ${toCardinal(wind.wind_direction_deg)}`}
          />
          <Metric label="Viento en contra" value={wind.average_headwind_factor.toFixed(2)} />
        </View>
      )}

      <Pressable
        onPress={onStartRoute}
        style={[styles.startButton, { backgroundColor: theme.text }]}>
        <ThemedText type="smallBold" style={{ color: theme.background }}>
          Iniciar Ruta
        </ThemedText>
      </Pressable>
    </ThemedView>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <ThemedText type="subtitle" style={styles.metricValue}>
        {value}
      </ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        {label}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: {
    borderTopLeftRadius: Spacing.four,
    borderTopRightRadius: Spacing.four,
    padding: Spacing.four,
    gap: Spacing.three,
    ...Platform.select({
      web: { boxShadow: '0px -4px 10px rgba(0,0,0,0.15)' },
      android: { elevation: 6 },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -4 },
        shadowOpacity: 0.15,
        shadowRadius: 10,
      },
    }),
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  metric: {
    alignItems: 'center',
    gap: Spacing.half,
  },
  metricValue: {
    fontSize: 22,
    lineHeight: 26,
  },
  startButton: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    alignItems: 'center',
  },
});

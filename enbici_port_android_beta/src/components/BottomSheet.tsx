import { Pressable, StyleSheet, Text, View } from "react-native";
import { GestureDetector, usePanGesture } from "react-native-gesture-handler";
import Animated, { useAnimatedStyle, useSharedValue, withSpring } from "react-native-reanimated";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { RouteResponse } from "../types/route";
import { cardShadow } from "./shadow";

const SHEET_HEIGHT = 260;
const PEEK = 90; // visible height when collapsed

const CARDINALS = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
const cardinal = (deg: number) => CARDINALS[Math.round(deg / 45) % 8];

export function BottomSheet({ route }: { route: RouteResponse }) {
  const { bottom } = useSafeAreaInsets();
  const collapsedY = SHEET_HEIGHT - PEEK;
  const y = useSharedValue(0);
  const start = useSharedValue(0);

  const pan = usePanGesture({
    onActivate: () => { "worklet"; start.value = y.value; },
    onUpdate: (e) => {
      "worklet";
      y.value = Math.min(collapsedY, Math.max(0, start.value + e.translationY));
    },
    onDeactivate: (e) => {
      "worklet";
      const target = y.value + e.velocityY * 0.1 > collapsedY / 2 ? collapsedY : 0;
      y.value = withSpring(target, { damping: 20 });
    },
  });

  const style = useAnimatedStyle(() => ({ transform: [{ translateY: y.value }] }));
  const minutes = Math.round((route.distance_km / 15) * 60);
  const w = route.wind_metrics;

  return (
    <View pointerEvents="box-none" style={StyleSheet.absoluteFill}>
      <Animated.View pointerEvents="auto" style={[styles.sheet, cardShadow, { height: SHEET_HEIGHT + bottom }, style]}>
        <GestureDetector gesture={pan}>
          <View style={styles.handleArea}><View style={styles.handle} /></View>
        </GestureDetector>
        <View style={styles.metrics}>
          <Metric label="Distancia" value={`${route.distance_km.toFixed(2)} km`} />
          <Metric label="Tiempo" value={`${minutes} min`} />
          <Metric label="Desnivel" value={`${Math.round(route.elevation_gain_m)} m`} />
        </View>
        {w && (
          <Text style={styles.wind}>
            Viento: {w.wind_speed_ms.toFixed(1)} m/s ({(w.wind_speed_ms * 3.6).toFixed(1)} km/h) del {cardinal(w.wind_direction_deg)}
          </Text>
        )}
        <Pressable style={styles.cta} onPress={() => {}}>
          <Text style={styles.ctaText}>Iniciar Ruta</Text>
        </Pressable>
      </Animated.View>
    </View>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metric}>
      <Text style={styles.value}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  sheet: { position: "absolute", left: 0, right: 0, bottom: 0, backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, paddingHorizontal: 16 },
  handleArea: { alignItems: "center", paddingVertical: 12 },
  handle: { width: 40, height: 5, borderRadius: 3, backgroundColor: "#ccc" },
  metrics: { flexDirection: "row", justifyContent: "space-around" },
  metric: { alignItems: "center" },
  value: { fontSize: 20, fontWeight: "700" },
  label: { fontSize: 12, color: "#666" },
  wind: { textAlign: "center", marginTop: 14, color: "#333" },
  cta: { backgroundColor: "#1b7f4b", borderRadius: 12, paddingVertical: 12, alignItems: "center", marginTop: 16 },
  ctaText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});

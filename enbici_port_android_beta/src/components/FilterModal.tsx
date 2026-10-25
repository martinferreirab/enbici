import Slider from "@react-native-community/slider";
import { useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, Switch, Text, View } from "react-native";
import { RouteFilters } from "../types/route";

interface Props {
  visible: boolean;
  filters: RouteFilters;
  onApply: (f: RouteFilters) => void;
  onClose: () => void;
}

export function FilterModal({ visible, filters, onApply, onClose }: Props) {
  const [f, setF] = useState(filters);
  useEffect(() => { if (visible) setF(filters); }, [visible, filters]);

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.sheet}>
          <Text style={styles.h}>Filtros de ruta</Text>

          <Text style={styles.label}>Evitar pendientes: {f.elevation_weight.toFixed(1)}</Text>
          <Slider minimumValue={0} maximumValue={10} step={0.5} value={f.elevation_weight}
            onValueChange={(v) => setF({ ...f, elevation_weight: v })} />

          <Text style={styles.label}>Evitar viento de frente: {f.wind_weight.toFixed(1)}</Text>
          <Slider minimumValue={0} maximumValue={10} step={0.5} value={f.wind_weight}
            onValueChange={(v) => setF({ ...f, wind_weight: v })} />

          <View style={styles.row}>
            <Text style={styles.label}>Permitir parques/plazas</Text>
            <Switch value={f.allow_parks} onValueChange={(v) => setF({ ...f, allow_parks: v })} />
          </View>

          <Text style={styles.label}>Cuadras en contramano permitidas</Text>
          <View style={styles.seg}>
            {([0, 1, 2, 3] as const).map((n) => (
              <Pressable key={n} style={[styles.segItem, f.max_against_traffic_blocks === n && styles.segOn]}
                onPress={() => setF({ ...f, max_against_traffic_blocks: n })}>
                <Text style={f.max_against_traffic_blocks === n ? styles.segTextOn : undefined}>{n}</Text>
              </Pressable>
            ))}
          </View>

          <Pressable style={styles.apply} onPress={() => onApply(f)}>
            <Text style={styles.applyText}>Aplicar</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.4)" },
  sheet: { backgroundColor: "#fff", borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, gap: 6 },
  h: { fontSize: 18, fontWeight: "700", marginBottom: 8 },
  label: { fontSize: 14, marginTop: 8 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginTop: 8 },
  seg: { flexDirection: "row", gap: 8, marginTop: 6 },
  segItem: { flex: 1, alignItems: "center", paddingVertical: 8, borderRadius: 8, backgroundColor: "#f1f3f4" },
  segOn: { backgroundColor: "#1b7f4b" },
  segTextOn: { color: "#fff", fontWeight: "600" },
  apply: { backgroundColor: "#1b7f4b", borderRadius: 10, paddingVertical: 12, alignItems: "center", marginTop: 16 },
  applyText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});

import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { cardShadow } from "./shadow";

interface Props {
  origin: string;
  dest: string;
  loading: boolean;
  onOrigin: (v: string) => void;
  onDest: (v: string) => void;
  onSearch: () => void;
  onFilters: () => void;
  onTitleLongPress: () => void;
}

export function TopSearchBar(p: Props) {
  const { top } = useSafeAreaInsets();
  return (
    <View pointerEvents="box-none" style={[styles.wrap, { paddingTop: top + 8 }]}>
      <View pointerEvents="auto" style={[styles.card, cardShadow]}>
        <View style={styles.header}>
          <Pressable onLongPress={p.onTitleLongPress} delayLongPress={600}>
            <Text style={styles.title}>enbici</Text>
          </Pressable>
          <Pressable onPress={p.onFilters} hitSlop={10}>
            <Text style={styles.icon}>⚙️ Filtros</Text>
          </Pressable>
        </View>
        <TextInput style={styles.input} placeholder="Origen (ej. Plaza Independencia)" value={p.origin} onChangeText={p.onOrigin} />
        <TextInput style={styles.input} placeholder="Destino (ej. Pocitos)" value={p.dest} onChangeText={p.onDest} onSubmitEditing={p.onSearch} returnKeyType="search" />
        <Pressable style={styles.button} onPress={p.onSearch} disabled={p.loading}>
          {p.loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Buscar ruta</Text>}
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { position: "absolute", top: 0, left: 0, right: 0, paddingHorizontal: 12 },
  card: { backgroundColor: "#fff", borderRadius: 16, padding: 12, gap: 8 },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { fontSize: 18, fontWeight: "700", color: "#1b7f4b" },
  icon: { fontSize: 14, color: "#333" },
  input: { backgroundColor: "#f1f3f4", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8, fontSize: 15 },
  button: { backgroundColor: "#1b7f4b", borderRadius: 10, paddingVertical: 10, alignItems: "center" },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
});

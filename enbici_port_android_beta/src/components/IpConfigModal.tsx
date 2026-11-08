import { useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { DEFAULT_API_BASE_URL } from "../config";

interface Props {
  visible: boolean;
  current: string;
  onSave: (value: string) => void;
  onClose: () => void;
}

export function IpConfigModal({ visible, current, onSave, onClose }: Props) {
  const [value, setValue] = useState(current);
  useEffect(() => { if (visible) setValue(current); }, [visible, current]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <View style={styles.box}>
          <Text style={styles.h}>IP del backend (WSL)</Text>
          <Text style={styles.hint}>Obtenela con `wsl hostname -I`. Ej: 172.30.108.170 (puerto 8000 por defecto)</Text>
          <TextInput style={styles.input} value={value} onChangeText={setValue} autoCapitalize="none" autoCorrect={false} keyboardType="url" />
          <View style={styles.row}>
            <Pressable onPress={() => setValue(DEFAULT_API_BASE_URL)}><Text style={styles.link}>Restablecer</Text></Pressable>
            <View style={styles.row}>
              <Pressable onPress={onClose}><Text style={styles.link}>Cancelar</Text></Pressable>
              <Pressable onPress={() => onSave(value)}><Text style={[styles.link, styles.bold]}>Guardar</Text></Pressable>
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "rgba(0,0,0,0.4)" },
  box: { backgroundColor: "#fff", borderRadius: 16, padding: 20, gap: 10 },
  h: { fontSize: 17, fontWeight: "700" },
  hint: { fontSize: 12, color: "#666" },
  input: { backgroundColor: "#f1f3f4", borderRadius: 10, padding: 10, fontSize: 15 },
  row: { flexDirection: "row", justifyContent: "space-between", gap: 20 },
  link: { color: "#1b7f4b", fontSize: 15 },
  bold: { fontWeight: "700" },
});

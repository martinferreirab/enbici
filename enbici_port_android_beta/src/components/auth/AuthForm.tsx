import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

export type AuthMode = "login" | "register";

interface Props {
  mode: AuthMode;
  loading: boolean;
  error: string | null;
  onSubmit: (username: string, password: string) => void;
  onToggleMode: () => void;
}

export function AuthForm({ mode, loading, error, onSubmit, onToggleMode }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const isLogin = mode === "login";
  const valid = username.trim().length >= 3 && password.length >= 6;

  return (
    <View style={styles.form}>
      <Text style={styles.title}>{isLogin ? "Iniciar sesión" : "Crear cuenta"}</Text>
      <Text style={styles.hint}>Para guardar rutas en tu historial.</Text>
      <TextInput
        style={styles.input} placeholder="Usuario" value={username} onChangeText={setUsername}
        autoCapitalize="none" autoCorrect={false} textContentType="username"
      />
      <TextInput
        style={styles.input} placeholder="Contraseña (mín. 6)" value={password} onChangeText={setPassword}
        secureTextEntry autoCapitalize="none" textContentType={isLogin ? "password" : "newPassword"}
        onSubmitEditing={() => valid && onSubmit(username.trim(), password)}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable
        style={[styles.cta, (!valid || loading) && styles.disabled]} disabled={!valid || loading}
        onPress={() => onSubmit(username.trim(), password)}
      >
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.ctaText}>{isLogin ? "Entrar" : "Registrarme"}</Text>}
      </Pressable>
      <Pressable onPress={onToggleMode}>
        <Text style={styles.link}>{isLogin ? "¿No tenés cuenta? Registrate" : "¿Ya tenés cuenta? Iniciá sesión"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: 10 },
  title: { fontSize: 18, fontWeight: "700" },
  hint: { fontSize: 12, color: "#666" },
  input: { backgroundColor: "#f1f3f4", borderRadius: 10, padding: 10, fontSize: 15 },
  error: { color: "#c62828", fontSize: 13 },
  cta: { backgroundColor: "#1b7f4b", borderRadius: 12, paddingVertical: 12, alignItems: "center", marginTop: 4 },
  disabled: { opacity: 0.5 },
  ctaText: { color: "#fff", fontWeight: "700", fontSize: 16 },
  link: { color: "#1b7f4b", fontSize: 14, textAlign: "center", marginTop: 4 },
});

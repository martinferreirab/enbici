import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { login, register } from "../../services/api";
import { saveToken } from "../../services/tokenStorage";
import { AuthForm, AuthMode } from "./AuthForm";

interface Props {
  visible: boolean;
  baseUrl: string;
  onClose: () => void;
  /** Called after the token is stored in SecureStore. */
  onAuthenticated: () => void;
}

export function AuthModal({ visible, baseUrl, onClose, onAuthenticated }: Props) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (visible) setError(null); }, [visible]);

  async function submit(username: string, password: string) {
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await (mode === "login" ? login : register)(baseUrl, username, password);
      await saveToken(access_token);
      onAuthenticated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.backdrop}>
        <View style={styles.box}>
          <AuthForm
            key={mode} mode={mode} loading={loading} error={error} onSubmit={submit}
            onToggleMode={() => { setError(null); setMode(mode === "login" ? "register" : "login"); }}
          />
          <Pressable onPress={onClose}><Text style={styles.cancel}>Cancelar</Text></Pressable>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: "rgba(0,0,0,0.4)" },
  box: { backgroundColor: "#fff", borderRadius: 16, padding: 20, gap: 14 },
  cancel: { color: "#666", fontSize: 14, textAlign: "center" },
});

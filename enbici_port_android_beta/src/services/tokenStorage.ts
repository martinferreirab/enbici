import * as SecureStore from "expo-secure-store";

const KEY = "enbici_jwt";

export const saveToken = (token: string) => SecureStore.setItemAsync(KEY, token);
export const clearToken = () => SecureStore.deleteItemAsync(KEY);

/** Reads `exp` from the JWT payload (no signature check; the backend is the authority). */
function isExpired(token: string): boolean {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const { exp } = JSON.parse(atob(b64));
    return typeof exp !== "number" || exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

/** Returns the stored token if present and not expired; otherwise clears it and returns null. */
export async function getValidToken(): Promise<string | null> {
  const token = await SecureStore.getItemAsync(KEY);
  if (!token) return null;
  if (isExpired(token)) {
    await clearToken();
    return null;
  }
  return token;
}

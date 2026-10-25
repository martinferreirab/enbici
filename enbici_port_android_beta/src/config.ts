import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";

const STORAGE_KEY = "enbici:api_base_url";

export const DEFAULT_API_BASE_URL =
  Platform.OS === "web" ? "http://localhost:8000" : "http://172.30.108.170:8000";

/** Accepts "172.30.1.5", "172.30.1.5:8000" or a full URL; returns a clean base URL. */
export function normalizeBaseUrl(input: string): string {
  let url = input.trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(url)) url = `http://${url}`;
  if (!/:\d+$/.test(url.replace(/^https?:\/\//i, "").split("/")[0])) url += ":8000";
  return url;
}

export async function getApiBaseUrl(): Promise<string> {
  const stored = await AsyncStorage.getItem(STORAGE_KEY);
  return stored || DEFAULT_API_BASE_URL;
}

export async function setApiBaseUrl(input: string): Promise<string> {
  const url = normalizeBaseUrl(input);
  await AsyncStorage.setItem(STORAGE_KEY, url);
  return url;
}

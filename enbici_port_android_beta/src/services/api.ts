import { AuthResponse, JourneyPayload, RouteRequestParams, RouteResponse, SavedJourney } from "../types/route";

export class NetworkError extends Error {}
export class BackendError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const TIMEOUT_MS = 90_000; // first request may rebuild graph / geocode

export async function fetchRoute(baseUrl: string, params: RouteRequestParams): Promise<RouteResponse> {
  const qs = Object.entries(params)
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join("&");
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${baseUrl}/route?${qs}`, { signal: ctrl.signal });
  } catch {
    throw new NetworkError(`No se pudo conectar al servidor (${baseUrl})`);
  } finally {
    clearTimeout(timer);
  }
  return parseResponse<RouteResponse>(res);
}

async function parseResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new BackendError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

/** JSON request to the backend; adds `Authorization: Bearer <token>` when a token is given. */
async function request<T>(baseUrl: string, path: string, init: { method?: string; body?: unknown; token?: string } = {}): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}`, {
      method: init.method ?? "GET",
      headers: {
        ...(init.body !== undefined && { "Content-Type": "application/json" }),
        ...(init.token && { Authorization: `Bearer ${init.token}` }),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      signal: ctrl.signal,
    });
  } catch {
    throw new NetworkError(`No se pudo conectar al servidor (${baseUrl})`);
  } finally {
    clearTimeout(timer);
  }
  return parseResponse<T>(res);
}

export const login = (baseUrl: string, username: string, password: string) =>
  request<AuthResponse>(baseUrl, "/login", { method: "POST", body: { username, password } });

export const register = (baseUrl: string, username: string, password: string) =>
  request<AuthResponse>(baseUrl, "/register", { method: "POST", body: { username, password } });

export const saveRoute = (baseUrl: string, token: string, journey: JourneyPayload) =>
  request<SavedJourney>(baseUrl, "/users/me/routes", { method: "POST", body: journey, token });

export const listRoutes = (baseUrl: string, token: string) =>
  request<SavedJourney[]>(baseUrl, "/users/me/routes", { token });

export const startJourney = (baseUrl: string, token: string, id: number) =>
  request<SavedJourney>(baseUrl, `/users/me/routes/${id}/start`, { method: "POST", token });

export const sendTelemetry = (baseUrl: string, token: string, id: number, body: { lat: number; lon: number; speed_ms: number | null }) =>
  request<{ status: string }>(baseUrl, `/users/me/routes/${id}/telemetry`, { method: "POST", body, token });

export const finishJourney = (baseUrl: string, token: string, id: number) =>
  request<SavedJourney>(baseUrl, `/users/me/routes/${id}/finish`, { method: "POST", token });

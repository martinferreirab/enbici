import { RouteRequestParams, RouteResponse } from "../types/route";

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
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new BackendError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

/** map_url is relative to the backend; the query param busts the WebView cache. */
export function resolveMapUrl(baseUrl: string, mapUrl: string): string {
  return `${baseUrl}${mapUrl}?t=${Date.now()}`;
}

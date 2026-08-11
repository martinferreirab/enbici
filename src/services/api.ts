import { API_BASE_URL } from '@/config';

export type RouteParams = {
  originPlace?: string;
  destPlace?: string;
  originLat?: number;
  originLon?: number;
  destLat?: number;
  destLon?: number;
  elevationWeight?: number;
  windWeight?: number;
  allowParks?: boolean;
  maxAgainstTrafficBlocks?: 0 | 1 | 2 | 3;
};

export type WindMetrics = {
  wind_speed_ms: number;
  wind_direction_deg: number;
  average_headwind_factor: number;
};

export type RouteResponse = {
  map_url: string;
  distance_km: number;
  elevation_gain_m: number;
  node_count: number;
  wind_metrics: WindMetrics | null;
};

export async function getRoute(params: RouteParams): Promise<RouteResponse> {
  const query = new URLSearchParams();

  if (params.originPlace) query.set('origin_place', params.originPlace);
  if (params.destPlace) query.set('dest_place', params.destPlace);
  if (params.originLat != null) query.set('origin_lat', String(params.originLat));
  if (params.originLon != null) query.set('origin_lon', String(params.originLon));
  if (params.destLat != null) query.set('dest_lat', String(params.destLat));
  if (params.destLon != null) query.set('dest_lon', String(params.destLon));
  query.set('elevation_weight', String(params.elevationWeight ?? 5.0));
  query.set('wind_weight', String(params.windWeight ?? 0.0));
  query.set('allow_parks', String(params.allowParks ?? true));
  query.set('max_against_traffic_blocks', String(params.maxAgainstTrafficBlocks ?? 0));

  const url = `${API_BASE_URL}/route?${query.toString()}`;
  let response: Response;

  try {
    response = await fetch(url);
  } catch (networkError) {
    console.error(
      `[api] Network/CORS error while fetching ${url}. ` +
        'Check that the backend is reachable at API_BASE_URL and that CORS is enabled.',
      networkError,
    );
    throw new Error('No se pudo conectar con el servidor. Verificá tu conexión e intentá de nuevo.');
  }

  if (!response.ok) {
    const message = await response.text().catch(() => response.statusText);
    console.error(`[api] Route request failed (${response.status}): ${message}`);
    throw new Error(`Route request failed (${response.status}): ${message}`);
  }

  return response.json();
}

export function resolveMapUrl(mapUrl: string): string {
  if (!mapUrl) {
    console.error('[api] resolveMapUrl received an empty map_url');
    return API_BASE_URL;
  }
  const resolved = mapUrl.startsWith('http') ? mapUrl : `${API_BASE_URL}${mapUrl}`;
  console.log(`[api] Resolved map URL: ${resolved}`);
  return resolved;
}

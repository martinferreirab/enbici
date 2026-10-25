export interface WindMetrics {
  wind_speed_ms: number;
  wind_direction_deg: number;
  average_headwind_factor: number;
}

export interface RouteResponse {
  distance_km: number;
  elevation_gain_m: number;
  node_count: number;
  map_url: string;
  wind_metrics: WindMetrics | null;
}

export interface RouteFilters {
  elevation_weight: number;
  wind_weight: number;
  allow_parks: boolean;
  max_against_traffic_blocks: 0 | 1 | 2 | 3;
}

export interface RouteRequestParams extends RouteFilters {
  origin_place: string;
  dest_place: string;
}

export const DEFAULT_FILTERS: RouteFilters = {
  elevation_weight: 5,
  wind_weight: 0,
  allow_parks: true,
  max_against_traffic_blocks: 0,
};

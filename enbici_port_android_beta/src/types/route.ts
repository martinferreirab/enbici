export interface WindMetrics {
  wind_speed_ms: number;
  wind_direction_deg: number;
  average_headwind_factor: number;
}

export interface Coordinate {
  lat: number;
  lon: number;
}

export interface RouteResponse {
  distance_km: number;
  elevation_gain_m: number;
  node_count: number;
  map_url: string | null;
  route_coordinates: Coordinate[];
  wind_metrics: WindMetrics | null;
  /** Fresh buses matched to the route's edges; null when bus_weight=0 or live bus data was unavailable. */
  live_buses_near_route: number | null;
}

export interface RouteFilters {
  elevation_weight: number;
  wind_weight: number;
  /** 0 = ignore buses; 1 = +15% (1-2 buses) / +30% (3+) per segment; 2 = double, etc. */
  bus_weight: number;
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
  bus_weight: 1,
  allow_parks: true,
  max_against_traffic_blocks: 0,
};

/** Journey saved by an authenticated user (POST /users/me/routes). */
export interface JourneyPayload extends RouteFilters {
  origin_place: string;
  dest_place: string;
  distance_km: number;
  elevation_gain_m: number;
}

export interface SavedJourney extends JourneyPayload {
  id: number;
  timestamp: string;
  is_started: boolean;
  is_completed: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  username: string;
}

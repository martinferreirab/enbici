import * as Location from "expo-location";
import { useCallback, useEffect, useRef, useState } from "react";
import { finishJourney, sendTelemetry, startJourney } from "../services/api";
import { Coordinate } from "../types/route";
import { haversineMeters } from "../utils/geo";

export const TELEMETRY_INTERVAL_MS = 15_000;
export const ARRIVAL_RADIUS_M = 20;

export class LocationPermissionError extends Error {}

/** GPS lifecycle of a journey: /start → telemetry every 15 s → /finish when within 20 m of the destination. */
export function useJourneyTracking(baseUrl: string) {
  const subscription = useRef<Location.LocationSubscription | null>(null);
  const [active, setActive] = useState(false);
  const [position, setPosition] = useState<Coordinate | null>(null);

  const stop = useCallback(() => {
    subscription.current?.remove();
    subscription.current = null;
    setActive(false);
  }, []);

  useEffect(() => stop, [stop]);

  const start = useCallback(
    async (journeyId: number, token: string, destination: Coordinate, onArrived: () => void) => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") throw new LocationPermissionError("Se necesita el permiso de ubicación para seguir la ruta.");

      await startJourney(baseUrl, token, journeyId);
      setActive(true);
      let arrived = false;

      subscription.current = await Location.watchPositionAsync(
        { accuracy: Location.Accuracy.High, timeInterval: TELEMETRY_INTERVAL_MS, distanceInterval: 0 },
        async ({ coords }) => {
          if (arrived) return;
          const here = { lat: coords.latitude, lon: coords.longitude };
          setPosition(here);
          const speed = coords.speed != null && coords.speed >= 0 ? coords.speed : null;
          sendTelemetry(baseUrl, token, journeyId, { ...here, speed_ms: speed }).catch(() => {}); // best-effort

          if (haversineMeters(here.lat, here.lon, destination.lat, destination.lon) < ARRIVAL_RADIUS_M) {
            arrived = true;
            stop();
            await finishJourney(baseUrl, token, journeyId).catch(() => {});
            onArrived();
          }
        },
      );
    },
    [baseUrl, stop],
  );

  return { active, position, start, stop };
}

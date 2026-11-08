import { useEffect, useRef } from "react";
import { StyleSheet } from "react-native";
import MapView, { Marker, Polyline, Region } from "react-native-maps";
import { Coordinate } from "../types/route";

const MONTEVIDEO: Region = { latitude: -34.9011, longitude: -56.1645, latitudeDelta: 0.12, longitudeDelta: 0.12 };
const TRACKING_ZOOM = 17;

interface Props {
  coordinates: Coordinate[];
  /** GPS tracking active: shows the user dot and keeps the camera on them, north up. */
  tracking: boolean;
  position: Coordinate | null;
}

const toLatLng = (c: Coordinate) => ({ latitude: c.lat, longitude: c.lon });

export function MapViewer({ coordinates, tracking, position }: Props) {
  const map = useRef<MapView>(null);
  const points = coordinates.map(toLatLng);

  // Frame the whole route when a new one arrives (bottom padding clears the sheet).
  useEffect(() => {
    if (points.length > 1 && !tracking) {
      map.current?.fitToCoordinates(points, { edgePadding: { top: 180, right: 50, bottom: 380, left: 50 }, animated: true });
    }
  }, [coordinates]); // eslint-disable-line react-hooks/exhaustive-deps

  // Follow the user with a fixed orientation (heading 0 = north up, flat).
  useEffect(() => {
    if (tracking && position) {
      map.current?.animateCamera({ center: toLatLng(position), heading: 0, pitch: 0, zoom: TRACKING_ZOOM }, { duration: 800 });
    }
  }, [tracking, position]);

  return (
    <MapView
      ref={map}
      style={StyleSheet.absoluteFill}
      initialRegion={MONTEVIDEO}
      showsUserLocation={tracking}
      showsMyLocationButton={false}
      toolbarEnabled={false}
      rotateEnabled={!tracking}
      pitchEnabled={!tracking}
    >
      {points.length > 1 && (
        <>
          <Polyline coordinates={points} strokeColor="#2563eb" strokeWidth={5} />
          <Marker coordinate={points[0]} title="Origen" pinColor="green" />
          <Marker coordinate={points[points.length - 1]} title="Destino" pinColor="red" />
        </>
      )}
    </MapView>
  );
}

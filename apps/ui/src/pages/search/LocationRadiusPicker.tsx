import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { LocationRadiusValue } from "./types";

const DEFAULT_RADIUS_KM = 50;
const EARTH_RADIUS_KM = 6371.0088;

export type LocationRadiusPickerProps = {
  value: LocationRadiusValue | null;
  onChange: (value: LocationRadiusValue) => void;
  onMapError?: (message: string) => void;
};

function toHandlePosition(center: LocationRadiusValue): L.LatLng {
  const latitudeRadians = (center.latitude * Math.PI) / 180;
  const angularDistance = center.radiusKm / EARTH_RADIUS_KM;
  const cosLatitude = Math.cos(latitudeRadians);
  const longitudeOffsetRadians =
    Math.abs(cosLatitude) < 1e-8 ? 0 : angularDistance / cosLatitude;
  const longitudeOffsetDegrees = (longitudeOffsetRadians * 180) / Math.PI;

  return L.latLng(center.latitude, center.longitude + longitudeOffsetDegrees);
}

function toCircleStyle() {
  return {
    color: "#2563eb",
    fillColor: "#60a5fa",
    fillOpacity: 0.15,
    weight: 2
  };
}

export function LocationRadiusPicker({ value, onChange, onMapError }: LocationRadiusPickerProps) {
  const mapElementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const centerMarkerRef = useRef<L.CircleMarker | null>(null);
  const radiusCircleRef = useRef<L.Circle | null>(null);
  const radiusHandleRef = useRef<L.Marker | null>(null);

  useEffect(() => {
    if (!mapElementRef.current || mapRef.current) {
      return;
    }

    const map = L.map(mapElementRef.current).setView([20, 0], 2);
    mapRef.current = map;

    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors"
    });
    tiles.on("tileerror", () => {
      onMapError?.("Map tiles failed to load. You can still use manual coordinate inputs.");
    });
    tiles.addTo(map);

    map.on("click", (event: L.LeafletMouseEvent) => {
      onChange({
        latitude: event.latlng.lat,
        longitude: event.latlng.lng,
        radiusKm: value?.radiusKm ?? DEFAULT_RADIUS_KM
      });
    });

    return () => {
      map.remove();
      mapRef.current = null;
      centerMarkerRef.current = null;
      radiusCircleRef.current = null;
      radiusHandleRef.current = null;
    };
  }, [onChange, onMapError, value?.radiusKm]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) {
      return;
    }

    centerMarkerRef.current?.remove();
    radiusCircleRef.current?.remove();
    radiusHandleRef.current?.remove();
    centerMarkerRef.current = null;
    radiusCircleRef.current = null;
    radiusHandleRef.current = null;

    if (!value) {
      return;
    }

    const center = L.latLng(value.latitude, value.longitude);
    const handle = toHandlePosition(value);

    const centerMarker = L.circleMarker(center, {
      radius: 5,
      color: "#1d4ed8",
      fillColor: "#2563eb",
      fillOpacity: 1,
      weight: 1
    }).addTo(map);
    centerMarkerRef.current = centerMarker;

    const radiusCircle = L.circle(center, {
      radius: value.radiusKm * 1000,
      ...toCircleStyle()
    }).addTo(map);
    radiusCircleRef.current = radiusCircle;

    const radiusHandle = L.marker(handle, {
      draggable: true,
      icon: L.divIcon({
        className: "search-location-radius-handle",
        iconSize: [14, 14]
      })
    }).addTo(map);
    radiusHandleRef.current = radiusHandle;

    radiusHandle.on("drag", (event: L.LeafletEvent) => {
      const marker = event.target as L.Marker;
      const markerPosition = marker.getLatLng();
      const nextRadiusKm = Math.max(map.distance(center, markerPosition) / 1000, 0.1);
      radiusCircle.setRadius(nextRadiusKm * 1000);
      onChange({
        latitude: value.latitude,
        longitude: value.longitude,
        radiusKm: nextRadiusKm
      });
    });

    map.setView(center, Math.max(map.getZoom(), 8));
  }, [onChange, value]);

  return <div className="search-location-map" ref={mapElementRef} aria-label="Location radius map" />;
}

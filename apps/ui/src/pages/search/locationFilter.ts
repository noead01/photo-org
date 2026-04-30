import type { LocationRadiusValue } from "./types";

export type ParsedLocationDraft = {
  latitude: number | null;
  longitude: number | null;
  radiusKm: number | null;
};

function parseNumericDraft(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function hasAnyLocationValue(parsed: ParsedLocationDraft): boolean {
  return parsed.latitude !== null || parsed.longitude !== null || parsed.radiusKm !== null;
}

export function parseLocationDraft(
  latitudeDraft: string,
  longitudeDraft: string,
  radiusDraft: string
): ParsedLocationDraft {
  return {
    latitude: parseNumericDraft(latitudeDraft),
    longitude: parseNumericDraft(longitudeDraft),
    radiusKm: parseNumericDraft(radiusDraft)
  };
}

export function validateLocationDraft(parsed: ParsedLocationDraft): string | null {
  if (!hasAnyLocationValue(parsed)) {
    return null;
  }

  if (parsed.latitude === null) {
    return "Latitude is required.";
  }

  if (!Number.isFinite(parsed.latitude)) {
    return "Latitude must be a number.";
  }

  if (parsed.latitude < -90 || parsed.latitude > 90) {
    return "Latitude must be between -90 and 90.";
  }

  if (parsed.longitude === null) {
    return "Longitude is required.";
  }

  if (!Number.isFinite(parsed.longitude)) {
    return "Longitude must be a number.";
  }

  if (parsed.longitude < -180 || parsed.longitude > 180) {
    return "Longitude must be between -180 and 180.";
  }

  if (parsed.radiusKm === null) {
    return "Radius (km) is required.";
  }

  if (!Number.isFinite(parsed.radiusKm)) {
    return "Radius (km) must be a number.";
  }

  if (parsed.radiusKm <= 0) {
    return "Radius (km) must be greater than 0.";
  }

  return null;
}

export function buildLocationRadiusFilter(
  parsed: ParsedLocationDraft
): { latitude: number; longitude: number; radius_km: number } | null {
  if (validateLocationDraft(parsed)) {
    return null;
  }

  if (
    parsed.latitude === null ||
    parsed.longitude === null ||
    parsed.radiusKm === null
  ) {
    return null;
  }

  return {
    latitude: parsed.latitude,
    longitude: parsed.longitude,
    radius_km: parsed.radiusKm
  };
}

export function formatLocationChipLabel(location: LocationRadiusValue): string {
  return `location: ${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)} (${location.radiusKm.toFixed(1)} km)`;
}

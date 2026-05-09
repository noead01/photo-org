import type { AlbumRecord } from "../library/libraryRouteApi";
import { DEFAULT_SEARCH_PAGE_LIMIT } from "../library/libraryRouteApi";
import { buildLibraryUrlQuery } from "../library/libraryRouteSearchState";

export function serializeSavedFilter(value: Record<string, unknown> | null | undefined): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "{}";
  }
  return JSON.stringify(value, null, 2);
}

export function parseSavedFilterDraft(raw: string): Record<string, unknown> {
  const parsed = JSON.parse(raw);
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("Saved filter JSON must be an object.");
  }
  return parsed as Record<string, unknown>;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  const seen = new Set<string>();
  const values: string[] = [];
  for (const entry of value) {
    if (typeof entry !== "string") {
      continue;
    }
    const trimmed = entry.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    values.push(trimmed);
  }
  return values;
}

function asBool(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function asFiniteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function buildLibraryQueryForAlbum(album: AlbumRecord): string {
  const defaultState = {
    queryChips: [],
    fromDate: "",
    toDate: "",
    selectedPersonNames: [] as string[],
    selectedAlbumIds: [] as string[],
    personCertaintyMode: "human_only" as const,
    suggestionConfidenceMinDraft: "0.8",
    locationRadius: null,
    hasFacesFilter: null,
    pathHintFilters: [] as string[],
    sortDirection: "desc" as const,
    page: 1,
    pageSize: DEFAULT_SEARCH_PAGE_LIMIT
  };

  if (album.kind === "editable") {
    return buildLibraryUrlQuery({
      ...defaultState,
      selectedAlbumIds: [album.album_id]
    });
  }

  const savedFilter = asRecord(album.saved_filter) ?? {};
  const dateFilter = asRecord(savedFilter.date);
  const fromDate = typeof dateFilter?.from === "string" ? dateFilter.from.trim() : "";
  const toDate = typeof dateFilter?.to === "string" ? dateFilter.to.trim() : "";

  const personCertaintyMode =
    savedFilter.person_certainty_mode === "include_suggestions"
      ? "include_suggestions"
      : "human_only";
  const suggestionConfidenceMin = asFiniteNumber(savedFilter.suggestion_confidence_min);
  const locationRadiusValue = asRecord(savedFilter.location_radius);
  const latitude = asFiniteNumber(locationRadiusValue?.latitude);
  const longitude = asFiniteNumber(locationRadiusValue?.longitude);
  const radiusKm = asFiniteNumber(locationRadiusValue?.radius_km);

  return buildLibraryUrlQuery({
    ...defaultState,
    fromDate,
    toDate,
    selectedPersonNames: asStringArray(savedFilter.person_names),
    selectedAlbumIds: asStringArray(savedFilter.album_ids),
    personCertaintyMode,
    suggestionConfidenceMinDraft:
      suggestionConfidenceMin !== null
        ? String(suggestionConfidenceMin)
        : defaultState.suggestionConfidenceMinDraft,
    locationRadius:
      latitude !== null && longitude !== null && radiusKm !== null
        ? {
            latitude,
            longitude,
            radius_km: radiusKm
          }
        : null,
    hasFacesFilter: asBool(savedFilter.has_faces),
    pathHintFilters: asStringArray(savedFilter.path_hints)
  });
}

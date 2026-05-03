import {
  buildLocationRadiusFilter,
  parseLocationDraft
} from "../search/locationFilter";
import { normalizePathHintFilters } from "../search/facetFilters";
import {
  dedupeTrimmedValues,
  parseNullableBooleanParam
} from "./urlSerialization";
import type {
  LibraryLocationRadius,
  PersonCertaintyMode,
  SearchUrlState
} from "./libraryRouteTypes";

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const DEFAULT_PERSON_CERTAINTY_MODE: PersonCertaintyMode = "human_only";
const DEFAULT_SUGGESTION_CONFIDENCE_MIN = "0.8";

function isValidIsoDate(value: string): boolean {
  if (!DATE_PATTERN.test(value)) {
    return false;
  }

  const [yearRaw, monthRaw, dayRaw] = value.split("-");
  const year = Number(yearRaw);
  const month = Number(monthRaw);
  const day = Number(dayRaw);
  if (!Number.isInteger(year) || !Number.isInteger(month) || !Number.isInteger(day)) {
    return false;
  }

  const parsed = new Date(Date.UTC(year, month - 1, day));
  return (
    parsed.getUTCFullYear() === year &&
    parsed.getUTCMonth() === month - 1 &&
    parsed.getUTCDate() === day
  );
}

function buildDateFilter(from: string, to: string): { from?: string; to?: string } | null {
  const trimmedFrom = from.trim();
  const trimmedTo = to.trim();

  if (!trimmedFrom && !trimmedTo) {
    return null;
  }

  return {
    ...(trimmedFrom ? { from: trimmedFrom } : {}),
    ...(trimmedTo ? { to: trimmedTo } : {})
  };
}

function normalizeForFuzzyMatch(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function parsePersonCertaintyMode(raw: string | null): PersonCertaintyMode {
  if (raw === "include_suggestions") {
    return "include_suggestions";
  }
  return DEFAULT_PERSON_CERTAINTY_MODE;
}

function parseSuggestionConfidenceMinDraft(raw: string | null): string {
  const candidate = (raw ?? "").trim();
  if (!candidate) {
    return DEFAULT_SUGGESTION_CONFIDENCE_MIN;
  }
  const parsed = Number(candidate);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    return DEFAULT_SUGGESTION_CONFIDENCE_MIN;
  }
  return candidate;
}

function normalizeSuggestionConfidenceMin(
  raw: string,
  fallback = Number(DEFAULT_SUGGESTION_CONFIDENCE_MIN)
): number {
  const parsed = Number(raw.trim());
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    return fallback;
  }
  return parsed;
}

export function isFuzzyNameMatch(query: string, candidate: string): boolean {
  const normalizedQuery = normalizeForFuzzyMatch(query);
  const normalizedCandidate = normalizeForFuzzyMatch(candidate);

  if (!normalizedQuery || !normalizedCandidate) {
    return false;
  }

  if (normalizedCandidate.includes(normalizedQuery)) {
    return true;
  }

  let queryIndex = 0;
  for (const character of normalizedCandidate) {
    if (character === normalizedQuery[queryIndex]) {
      queryIndex += 1;
      if (queryIndex === normalizedQuery.length) {
        return true;
      }
    }
  }

  return false;
}

export function parseLibraryUrlState(search: string): SearchUrlState {
  const params = new URLSearchParams(search);
  const queryChips = dedupeTrimmedValues(params.getAll("query"));

  const fromCandidate = (params.get("from") ?? "").trim();
  const toCandidate = (params.get("to") ?? "").trim();
  const fromDate = isValidIsoDate(fromCandidate) ? fromCandidate : "";
  const toDate = isValidIsoDate(toCandidate) ? toCandidate : "";

  const selectedPersonNames = dedupeTrimmedValues(params.getAll("person"));
  const personCertaintyMode = parsePersonCertaintyMode(params.get("personCertainty"));
  const suggestionConfidenceMinDraft = parseSuggestionConfidenceMinDraft(params.get("suggestionMin"));
  const pathHintFilters = normalizePathHintFilters(params.getAll("pathHint"));
  const hasFacesFilter = parseNullableBooleanParam(params.get("hasFaces"));

  const latitudeCandidate = (params.get("lat") ?? "").trim();
  const longitudeCandidate = (params.get("lng") ?? "").trim();
  const radiusCandidate = (params.get("radiusKm") ?? "").trim();
  const parsedLocation = parseLocationDraft(
    latitudeCandidate,
    longitudeCandidate,
    radiusCandidate
  );
  const locationRadius = buildLocationRadiusFilter(parsedLocation);
  const locationDrafts = locationRadius
    ? {
        latitudeDraft: String(locationRadius.latitude),
        longitudeDraft: String(locationRadius.longitude),
        radiusDraft: String(locationRadius.radius_km)
      }
    : { latitudeDraft: "", longitudeDraft: "", radiusDraft: "" };

  return {
    queryChips,
    fromDate,
    toDate,
    selectedPersonNames,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    latitudeDraft: locationDrafts.latitudeDraft,
    longitudeDraft: locationDrafts.longitudeDraft,
    radiusDraft: locationDrafts.radiusDraft,
    locationRadius,
    hasFacesFilter,
    pathHintFilters
  };
}

export function buildLibraryUrlQuery(state: {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
  locationRadius: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  page: number;
}): string {
  const params = new URLSearchParams();

  for (const chip of state.queryChips) {
    params.append("query", chip);
  }
  if (state.fromDate) {
    params.set("from", state.fromDate);
  }
  if (state.toDate) {
    params.set("to", state.toDate);
  }
  for (const personName of state.selectedPersonNames) {
    params.append("person", personName);
  }
  if (state.selectedPersonNames.length > 0) {
    params.set("personCertainty", state.personCertaintyMode);
    if (state.personCertaintyMode === "include_suggestions") {
      params.set(
        "suggestionMin",
        String(normalizeSuggestionConfidenceMin(state.suggestionConfidenceMinDraft))
      );
    }
  }
  if (state.locationRadius) {
    params.set("lat", String(state.locationRadius.latitude));
    params.set("lng", String(state.locationRadius.longitude));
    params.set("radiusKm", String(state.locationRadius.radius_km));
  }
  if (state.hasFacesFilter !== null) {
    params.set("hasFaces", state.hasFacesFilter ? "true" : "false");
  }
  for (const pathHint of state.pathHintFilters) {
    params.append("pathHint", pathHint);
  }
  if (state.page > 1) {
    params.set("page", String(state.page));
  }

  return params.toString();
}

export function validateDateRange(from: string, to: string): string | null {
  if (from && to && from > to) {
    return "From date must be on or before To date.";
  }

  return null;
}

export function buildSearchFilters(
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  personCertaintyMode: PersonCertaintyMode,
  suggestionConfidenceMinDraft: string,
  locationRadius: LibraryLocationRadius | null,
  hasFaces: boolean | null,
  pathHints: string[]
): {
  date?: { from?: string; to?: string };
  person_names?: string[];
  person_certainty_mode?: PersonCertaintyMode;
  suggestion_confidence_min?: number;
  location_radius?: LibraryLocationRadius;
  has_faces?: boolean;
  path_hints?: string[];
} | null {
  const dateFilter = buildDateFilter(fromDate, toDate);
  const personNameFilter = selectedPersonNames.length > 0 ? selectedPersonNames : null;
  const locationFilter = locationRadius;
  const pathHintFilter = pathHints.length > 0 ? pathHints : null;

  if (!dateFilter && !personNameFilter && !locationFilter && hasFaces === null && !pathHintFilter) {
    return null;
  }

  return {
    ...(dateFilter ? { date: dateFilter } : {}),
    ...(personNameFilter ? { person_names: personNameFilter } : {}),
    ...(personNameFilter ? { person_certainty_mode: personCertaintyMode } : {}),
    ...(personNameFilter && personCertaintyMode === "include_suggestions"
      ? { suggestion_confidence_min: normalizeSuggestionConfidenceMin(suggestionConfidenceMinDraft) }
      : {}),
    ...(locationFilter ? { location_radius: locationFilter } : {}),
    ...(hasFaces === null ? {} : { has_faces: hasFaces }),
    ...(pathHintFilter ? { path_hints: pathHintFilter } : {})
  };
}

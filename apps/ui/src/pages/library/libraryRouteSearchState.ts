import {
  buildLocationRadiusFilter,
  parseLocationDraft
} from "../search/locationFilter";
import { normalizePathHintFilters } from "../search/facetFilters";
import {
  dedupeTrimmedValues,
  parsePageSizeParam,
  parseNullableBooleanParam
} from "./urlSerialization";
import type {
  LibraryFacesFilterState,
  LibraryLocationRadius,
  PersonCertaintyMode,
  SortDirection,
  SearchUrlState
} from "./libraryRouteTypes";
import {
  DEFAULT_SEARCH_PAGE_LIMIT,
  SEARCH_PAGE_LIMIT_OPTIONS
} from "./libraryPageSize";

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const DEFAULT_PERSON_CERTAINTY_MODE: PersonCertaintyMode = "human_only";
const DEFAULT_SUGGESTION_CONFIDENCE_MIN = "0.8";
const DEFAULT_SORT_DIRECTION: SortDirection = "desc";
const MIN_FACES_BOUND = 0;
const MAX_FACES_BOUND = 10;
const DEFAULT_FACES_FILTER: LibraryFacesFilterState = {
  minCount: 0,
  maxCount: null,
  certaintyMinPct: 0,
  certaintyMaxPct: 100,
  hasUnknownPerson: false
};

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

function parseSortDirection(raw: string | null): SortDirection {
  if (raw === "asc") {
    return "asc";
  }
  return DEFAULT_SORT_DIRECTION;
}

function parseIntegerInRange(
  raw: string | null,
  minValue: number,
  maxValue: number
): number | null {
  if (raw === null) {
    return null;
  }
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < minValue || parsed > maxValue) {
    return null;
  }
  return parsed;
}

function parseBooleanFlag(raw: string | null): boolean {
  if (raw === null) {
    return false;
  }
  const normalized = raw.trim().toLowerCase();
  return normalized === "1" || normalized === "true";
}

function parseFacesFilterState(params: URLSearchParams): LibraryFacesFilterState {
  const parsedMin = parseIntegerInRange(params.get("facesMin"), MIN_FACES_BOUND, MAX_FACES_BOUND);
  const parsedMax = parseIntegerInRange(params.get("facesMax"), MIN_FACES_BOUND, MAX_FACES_BOUND);
  const parsedCertaintyMin = parseIntegerInRange(params.get("facesCertMin"), 0, 100);
  const parsedCertaintyMax = parseIntegerInRange(params.get("facesCertMax"), 0, 100);

  const normalizedMinCount = parsedMin ?? DEFAULT_FACES_FILTER.minCount;
  const normalizedMaxCount =
    parsedMax === null || parsedMax >= MAX_FACES_BOUND ? null : parsedMax;
  const minCount =
    normalizedMaxCount !== null && normalizedMinCount > normalizedMaxCount
      ? normalizedMaxCount
      : normalizedMinCount;

  const certaintyMinPct = parsedCertaintyMin ?? DEFAULT_FACES_FILTER.certaintyMinPct;
  const certaintyMaxPct = parsedCertaintyMax ?? DEFAULT_FACES_FILTER.certaintyMaxPct;

  return {
    minCount,
    maxCount: normalizedMaxCount,
    certaintyMinPct: Math.min(certaintyMinPct, certaintyMaxPct),
    certaintyMaxPct: Math.max(certaintyMinPct, certaintyMaxPct),
    hasUnknownPerson: parseBooleanFlag(params.get("facesUnknown"))
  };
}

function isZeroFacesOnly(facesFilter: LibraryFacesFilterState): boolean {
  return facesFilter.minCount === 0 && facesFilter.maxCount === 0;
}

function normalizeFacesFilterForPayload(
  facesFilter: LibraryFacesFilterState
):
  | {
      min_count?: number;
      max_count?: number;
      top_certainty_min?: number;
      top_certainty_max?: number;
      has_unknown_person?: boolean;
    }
  | null {
  const payload: {
    min_count?: number;
    max_count?: number;
    top_certainty_min?: number;
    top_certainty_max?: number;
    has_unknown_person?: boolean;
  } = {};

  const includeZeroFacesRange = isZeroFacesOnly(facesFilter);
  if (facesFilter.minCount > 0 || includeZeroFacesRange) {
    payload.min_count = facesFilter.minCount;
  }
  if (facesFilter.maxCount !== null || includeZeroFacesRange) {
    payload.max_count = facesFilter.maxCount ?? 0;
  }

  if (!includeZeroFacesRange) {
    if (facesFilter.certaintyMinPct > 0) {
      payload.top_certainty_min = facesFilter.certaintyMinPct / 100;
    }
    if (facesFilter.certaintyMaxPct < 100) {
      payload.top_certainty_max = facesFilter.certaintyMaxPct / 100;
    }
    if (facesFilter.hasUnknownPerson) {
      payload.has_unknown_person = true;
    }
  }

  return Object.keys(payload).length > 0 ? payload : null;
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

export function resolvePersonCertaintyPercent(
  personCertaintyMode: PersonCertaintyMode,
  suggestionConfidenceMinDraft: string
): number {
  if (personCertaintyMode === "human_only") {
    return 100;
  }

  return Math.round(normalizeSuggestionConfidenceMin(suggestionConfidenceMinDraft) * 100);
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
  const selectedAlbumIds = dedupeTrimmedValues(params.getAll("album"));
  const personCertaintyMode = parsePersonCertaintyMode(params.get("personCertainty"));
  const suggestionConfidenceMinDraft = parseSuggestionConfidenceMinDraft(params.get("suggestionMin"));
  const pathHintFilters = normalizePathHintFilters(params.getAll("pathHint"));
  const hasFacesFilter = parseNullableBooleanParam(params.get("hasFaces"));
  const facesFilter = parseFacesFilterState(params);

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
    sortDirection: parseSortDirection(params.get("sort")),
    pageSize: parsePageSizeParam(
      params.get("pageSize"),
      SEARCH_PAGE_LIMIT_OPTIONS,
      DEFAULT_SEARCH_PAGE_LIMIT
    ),
    selectedPersonNames,
    selectedAlbumIds,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    latitudeDraft: locationDrafts.latitudeDraft,
    longitudeDraft: locationDrafts.longitudeDraft,
    radiusDraft: locationDrafts.radiusDraft,
    locationRadius,
    hasFacesFilter,
    pathHintFilters,
    facesFilter
  };
}

export function buildLibraryUrlQuery(state: {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  selectedAlbumIds: string[];
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
  locationRadius: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  facesFilter?: LibraryFacesFilterState;
  sortDirection: SortDirection;
  page: number;
  pageSize: number;
}): string {
  const params = new URLSearchParams();
  const facesFilter = state.facesFilter ?? DEFAULT_FACES_FILTER;

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
  for (const albumId of state.selectedAlbumIds) {
    params.append("album", albumId);
  }
  const shouldPersistPersonCertainty =
    state.selectedPersonNames.length > 0 || state.personCertaintyMode !== DEFAULT_PERSON_CERTAINTY_MODE;
  if (shouldPersistPersonCertainty) {
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
  if (facesFilter.minCount > 0) {
    params.set("facesMin", String(facesFilter.minCount));
  }
  if (facesFilter.maxCount !== null) {
    params.set("facesMax", String(facesFilter.maxCount));
  }
  if (!isZeroFacesOnly(facesFilter)) {
    if (facesFilter.certaintyMinPct > 0) {
      params.set("facesCertMin", String(facesFilter.certaintyMinPct));
    }
    if (facesFilter.certaintyMaxPct < 100) {
      params.set("facesCertMax", String(facesFilter.certaintyMaxPct));
    }
    if (facesFilter.hasUnknownPerson) {
      params.set("facesUnknown", "1");
    }
  }
  if (state.sortDirection !== DEFAULT_SORT_DIRECTION) {
    params.set("sort", state.sortDirection);
  }
  if (state.page > 1) {
    params.set("page", String(state.page));
  }
  if (state.pageSize !== DEFAULT_SEARCH_PAGE_LIMIT) {
    params.set("pageSize", String(state.pageSize));
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
  selectedAlbumIds: string[],
  personCertaintyMode: PersonCertaintyMode,
  suggestionConfidenceMinDraft: string,
  locationRadius: LibraryLocationRadius | null,
  hasFaces: boolean | null,
  pathHints: string[],
  facesFilter: LibraryFacesFilterState = DEFAULT_FACES_FILTER
): {
  date?: { from?: string; to?: string };
  person_names?: string[];
  album_ids?: string[];
  person_certainty_mode?: PersonCertaintyMode;
  suggestion_confidence_min?: number;
  location_radius?: LibraryLocationRadius;
  has_faces?: boolean;
  path_hints?: string[];
  faces?: {
    min_count?: number;
    max_count?: number;
    top_certainty_min?: number;
    top_certainty_max?: number;
    has_unknown_person?: boolean;
  };
} | null {
  const dateFilter = buildDateFilter(fromDate, toDate);
  const personNameFilter = selectedPersonNames.length > 0 ? selectedPersonNames : null;
  const albumIdFilter = selectedAlbumIds.length > 0 ? selectedAlbumIds : null;
  const locationFilter = locationRadius;
  const pathHintFilter = pathHints.length > 0 ? pathHints : null;
  const facesPayload = normalizeFacesFilterForPayload(facesFilter);

  if (
    !dateFilter &&
    !personNameFilter &&
    !albumIdFilter &&
    !locationFilter &&
    hasFaces === null &&
    !pathHintFilter &&
    !facesPayload
  ) {
    return null;
  }

  return {
    ...(dateFilter ? { date: dateFilter } : {}),
    ...(personNameFilter ? { person_names: personNameFilter } : {}),
    ...(albumIdFilter ? { album_ids: albumIdFilter } : {}),
    ...(personNameFilter ? { person_certainty_mode: personCertaintyMode } : {}),
    ...(personNameFilter && personCertaintyMode === "include_suggestions"
      ? { suggestion_confidence_min: normalizeSuggestionConfidenceMin(suggestionConfidenceMinDraft) }
      : {}),
    ...(locationFilter ? { location_radius: locationFilter } : {}),
    ...(hasFaces === null ? {} : { has_faces: hasFaces }),
    ...(pathHintFilter ? { path_hints: pathHintFilter } : {}),
    ...(facesPayload ? { faces: facesPayload } : {})
  };
}

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LocationRadiusPicker } from "./search/LocationRadiusPicker";
import { FacetFilterPanel } from "./search/FacetFilterPanel";
import {
  normalizePathHintFilters,
  parseHasFacesFacetCounts,
  toPathHintFacetCounts,
  type FacetCountEntry,
  type SearchFacetPayload
} from "./search/facetFilters";
import {
  buildLocationRadiusFilter,
  formatLocationChipLabel,
  parseLocationDraft,
  validateLocationDraft
} from "./search/locationFilter";
import type { LocationRadiusValue } from "./search/types";

type SearchPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    cursor: string | null;
    items: SearchPhoto[];
  };
  facets?: SearchFacetPayload;
};

type PersonRecord = {
  person_id: string;
  display_name: string;
};

type SortDirection = "asc" | "desc";

const DEFAULT_SORT_DIRECTION: SortDirection = "desc";
const PAGE_LIMIT = 24;
const INVALID_PAGE_MESSAGE = "Reset to page 1 because that page position is unavailable.";
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

type SearchUrlState = {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  latitudeDraft: string;
  longitudeDraft: string;
  radiusDraft: string;
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
};

type SearchRequestSnapshot = {
  chips: string[];
  fromDate: string;
  toDate: string;
  personNames: string[];
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null;
  hasFaces: boolean | null;
  pathHints: string[];
  sortDirection: SortDirection;
  page: number;
  cursorByPage: Record<number, string | null>;
};

function buildFirstPageCursorMap(nextCursor: string | null): Record<number, string | null> {
  const cursorMap: Record<number, string | null> = { 1: null };
  if (nextCursor !== null) {
    cursorMap[2] = nextCursor;
  }
  return cursorMap;
}

function hasActiveSearchCriteria(snapshot: SearchRequestSnapshot): boolean {
  return (
    snapshot.chips.length > 0 ||
    Boolean(snapshot.fromDate || snapshot.toDate) ||
    snapshot.personNames.length > 0 ||
    snapshot.locationRadius !== null ||
    snapshot.hasFaces !== null ||
    snapshot.pathHints.length > 0
  );
}

function dedupeTrimmedValues(values: string[]): string[] {
  const seen = new Set<string>();
  const deduped: string[] = [];

  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    deduped.push(trimmed);
  }

  return deduped;
}

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

function parseSearchUrlState(search: string): SearchUrlState {
  const params = new URLSearchParams(search);
  const queryChips = dedupeTrimmedValues(params.getAll("query"));

  const fromCandidate = (params.get("from") ?? "").trim();
  const toCandidate = (params.get("to") ?? "").trim();
  const fromDate = isValidIsoDate(fromCandidate) ? fromCandidate : "";
  const toDate = isValidIsoDate(toCandidate) ? toCandidate : "";

  const selectedPersonNames = dedupeTrimmedValues(params.getAll("person"));
  const pathHintFilters = normalizePathHintFilters(params.getAll("pathHint"));

  const rawHasFaces = (params.get("hasFaces") ?? "").trim();
  const hasFacesFilter =
    rawHasFaces === "true" ? true : rawHasFaces === "false" ? false : null;

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
    latitudeDraft: locationDrafts.latitudeDraft,
    longitudeDraft: locationDrafts.longitudeDraft,
    radiusDraft: locationDrafts.radiusDraft,
    locationRadius,
    hasFacesFilter,
    pathHintFilters
  };
}

function buildSearchUrlQuery(state: {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
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

  return params.toString();
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

function validateDateRange(from: string, to: string): string | null {
  if (from && to && from > to) {
    return "From date must be on or before To date.";
  }

  return null;
}

function normalizeForFuzzyMatch(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isFuzzyNameMatch(query: string, candidate: string): boolean {
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

function buildSearchFilters(
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null,
  hasFaces: boolean | null,
  pathHints: string[]
): {
  date?: { from?: string; to?: string };
  person_names?: string[];
  location_radius?: { latitude: number; longitude: number; radius_km: number };
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
    ...(locationFilter ? { location_radius: locationFilter } : {}),
    ...(hasFaces === null ? {} : { has_faces: hasFaces }),
    ...(pathHintFilter ? { path_hints: pathHintFilter } : {})
  };
}

async function fetchSearchResults(
  query: string,
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null,
  hasFaces: boolean | null,
  pathHints: string[],
  sortDirection: SortDirection,
  cursor: string | null
): Promise<SearchResponsePayload> {
  const searchFilters = buildSearchFilters(
    fromDate,
    toDate,
    selectedPersonNames,
    locationRadius,
    hasFaces,
    pathHints
  );
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      q: query,
      ...(searchFilters ? { filters: searchFilters } : {}),
      sort: {
        by: "shot_ts",
        dir: sortDirection
      },
      page: {
        limit: PAGE_LIMIT,
        cursor
      }
    })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

export function SearchRoutePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const suppressNextUrlStateSyncRef = useRef(false);
  const applyingParsedUrlStateRef = useRef(false);

  const [draftQuery, setDraftQuery] = useState("");
  const [queryChips, setQueryChips] = useState<string[]>([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [personDraft, setPersonDraft] = useState("");
  const [selectedPersonNames, setSelectedPersonNames] = useState<string[]>([]);
  const [latitudeDraft, setLatitudeDraft] = useState("");
  const [longitudeDraft, setLongitudeDraft] = useState("");
  const [radiusDraft, setRadiusDraft] = useState("");
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const [personMessage, setPersonMessage] = useState<string | null>(null);
  const [mapMessage, setMapMessage] = useState<string | null>(null);
  const [hasFacesFilter, setHasFacesFilter] = useState<boolean | null>(null);
  const [pathHintFilters, setPathHintFilters] = useState<string[]>([]);
  const [facetHasFacesCounts, setFacetHasFacesCounts] = useState<{ true: number; false: number }>({
    true: 0,
    false: 0
  });
  const [facetPathHintCounts, setFacetPathHintCounts] = useState<FacetCountEntry[]>([]);
  const [results, setResults] = useState<SearchPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [sortDirection, setSortDirection] = useState<SortDirection>(DEFAULT_SORT_DIRECTION);
  const [page, setPage] = useState(1);
  const [cursorByPage, setCursorByPage] = useState<Record<number, string | null>>({ 1: null });
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [paginationMessage, setPaginationMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRequested, setHasRequested] = useState(false);
  const [lastFailedRequest, setLastFailedRequest] = useState<SearchRequestSnapshot | null>(null);
  const [lastSuccessfulHadCriteria, setLastSuccessfulHadCriteria] = useState(false);
  const parsedUrlState = useMemo(() => parseSearchUrlState(location.search), [location.search]);

  const serializedQuery = useMemo(() => queryChips.join(" "), [queryChips]);
  const dateRangeError = useMemo(() => validateDateRange(fromDate, toDate), [fromDate, toDate]);
  const parsedLocation = useMemo(
    () => parseLocationDraft(latitudeDraft, longitudeDraft, radiusDraft),
    [latitudeDraft, longitudeDraft, radiusDraft]
  );
  const locationError = useMemo(() => validateLocationDraft(parsedLocation), [parsedLocation]);
  const locationRadiusFilter = useMemo(
    () => buildLocationRadiusFilter(parsedLocation),
    [parsedLocation]
  );
  const hasActiveDateFilter = Boolean(fromDate || toDate);
  const hasActivePersonFilter = selectedPersonNames.length > 0;
  const hasActiveLocationFilter = Boolean(locationRadiusFilter);
  const hasActiveHasFacesFilter = hasFacesFilter !== null;
  const hasActivePathHintFilter = pathHintFilters.length > 0;
  const matchingPeople = useMemo(() => {
    const trimmed = personDraft.trim();
    if (!trimmed) {
      return [] as PersonRecord[];
    }

    return peopleDirectory.filter(
      (person) =>
        !selectedPersonNames.includes(person.display_name) &&
        isFuzzyNameMatch(trimmed, person.display_name)
    );
  }, [peopleDirectory, personDraft, selectedPersonNames]);

  useEffect(() => {
    let isCanceled = false;

    async function loadPeopleDirectory() {
      try {
        const response = await fetch("/api/v1/people");
        if (!response.ok) {
          throw new Error();
        }
        const payload = (await response.json()) as PersonRecord[];
        if (!isCanceled) {
          setPeopleDirectory(payload);
        }
      } catch {
        if (!isCanceled) {
          setPersonMessage("People lookup is unavailable. Search can continue without person filters.");
        }
      }
    }

    void loadPeopleDirectory();

    return () => {
      isCanceled = true;
    };
  }, []);

  useEffect(() => {
    if (suppressNextUrlStateSyncRef.current) {
      suppressNextUrlStateSyncRef.current = false;
      return;
    }

    applyingParsedUrlStateRef.current = true;
    setQueryChips(parsedUrlState.queryChips);
    setDraftQuery("");
    setFromDate(parsedUrlState.fromDate);
    setToDate(parsedUrlState.toDate);
    setSelectedPersonNames(parsedUrlState.selectedPersonNames);
    setPersonDraft("");
    setPersonMessage(null);
    setLatitudeDraft(parsedUrlState.latitudeDraft);
    setLongitudeDraft(parsedUrlState.longitudeDraft);
    setRadiusDraft(parsedUrlState.radiusDraft);
    setMapMessage(null);
    setHasFacesFilter(parsedUrlState.hasFacesFilter);
    setPathHintFilters(parsedUrlState.pathHintFilters);

    setIsLoading(false);
    setError(null);
    setHasRequested(false);
    setLastFailedRequest(null);
    setLastSuccessfulHadCriteria(false);
    setSortDirection(DEFAULT_SORT_DIRECTION);
    setPage(1);
    setCursorByPage({ 1: null });
    setNextCursor(null);
    setPaginationMessage(null);
    setResults([]);
    setTotalCount(0);
    setFacetHasFacesCounts({ true: 0, false: 0 });
    setFacetPathHintCounts(
      parsedUrlState.pathHintFilters.map((value) => ({
        value,
        count: 0
      }))
    );
  }, [parsedUrlState]);

  useEffect(() => {
    if (applyingParsedUrlStateRef.current) {
      applyingParsedUrlStateRef.current = false;
      return;
    }

    const nextQuery = buildSearchUrlQuery({
      queryChips,
      fromDate,
      toDate,
      selectedPersonNames,
      locationRadius: locationRadiusFilter,
      hasFacesFilter,
      pathHintFilters
    });
    const currentQuery = location.search.startsWith("?")
      ? location.search.slice(1)
      : location.search;

    if (nextQuery === currentQuery) {
      return;
    }

    suppressNextUrlStateSyncRef.current = true;
    navigate(
      {
        pathname: location.pathname,
        search: nextQuery ? `?${nextQuery}` : ""
      },
      { replace: true }
    );
  }, [
    fromDate,
    hasFacesFilter,
    location.pathname,
    location.search,
    locationRadiusFilter,
    navigate,
    pathHintFilters,
    queryChips,
    selectedPersonNames,
    toDate
  ]);

  function createSearchSnapshot(snapshot: SearchRequestSnapshot): SearchRequestSnapshot {
    return {
      chips: [...snapshot.chips],
      fromDate: snapshot.fromDate,
      toDate: snapshot.toDate,
      personNames: [...snapshot.personNames],
      locationRadius: snapshot.locationRadius ? { ...snapshot.locationRadius } : null,
      hasFaces: snapshot.hasFaces,
      pathHints: [...snapshot.pathHints],
      sortDirection: snapshot.sortDirection,
      page: snapshot.page,
      cursorByPage: { ...snapshot.cursorByPage }
    };
  }

  async function runSearch(snapshot: SearchRequestSnapshot) {
    if (validateDateRange(snapshot.fromDate, snapshot.toDate)) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setHasRequested(true);
    setPaginationMessage(null);

    try {
      const hadCriteria = hasActiveSearchCriteria(snapshot);
      const cursor = snapshot.cursorByPage[snapshot.page];
      if (snapshot.page > 1 && cursor === undefined) {
        setPaginationMessage(INVALID_PAGE_MESSAGE);
        const resetSnapshot = createSearchSnapshot({
          ...snapshot,
          page: 1,
          cursorByPage: { 1: null }
        });
        setPage(1);
        setCursorByPage(resetSnapshot.cursorByPage);
        const resetPayload = await fetchSearchResults(
          resetSnapshot.chips.join(" "),
          resetSnapshot.fromDate,
          resetSnapshot.toDate,
          resetSnapshot.personNames,
          resetSnapshot.locationRadius,
          resetSnapshot.hasFaces,
          resetSnapshot.pathHints,
          resetSnapshot.sortDirection,
          null
        );
        setResults(resetPayload.hits.items);
        setTotalCount(resetPayload.hits.total);
        setNextCursor(resetPayload.hits.cursor);
        setLastFailedRequest(null);
        setLastSuccessfulHadCriteria(hasActiveSearchCriteria(resetSnapshot));
        setFacetHasFacesCounts(parseHasFacesFacetCounts(resetPayload.facets));
        setFacetPathHintCounts(toPathHintFacetCounts(resetPayload.facets, resetSnapshot.pathHints));
        setCursorByPage(buildFirstPageCursorMap(resetPayload.hits.cursor));
        return;
      }

      const payload = await fetchSearchResults(
        snapshot.chips.join(" "),
        snapshot.fromDate,
        snapshot.toDate,
        snapshot.personNames,
        snapshot.locationRadius,
        snapshot.hasFaces,
        snapshot.pathHints,
        snapshot.sortDirection,
        cursor ?? null
      );
      if (snapshot.page > 1 && payload.hits.items.length === 0) {
        setPaginationMessage(INVALID_PAGE_MESSAGE);
        const resetSnapshot = createSearchSnapshot({
          ...snapshot,
          page: 1,
          cursorByPage: { 1: null }
        });
        setPage(1);
        setCursorByPage(resetSnapshot.cursorByPage);
        const resetPayload = await fetchSearchResults(
          resetSnapshot.chips.join(" "),
          resetSnapshot.fromDate,
          resetSnapshot.toDate,
          resetSnapshot.personNames,
          resetSnapshot.locationRadius,
          resetSnapshot.hasFaces,
          resetSnapshot.pathHints,
          resetSnapshot.sortDirection,
          null
        );
        setResults(resetPayload.hits.items);
        setTotalCount(resetPayload.hits.total);
        setNextCursor(resetPayload.hits.cursor);
        setLastFailedRequest(null);
        setLastSuccessfulHadCriteria(hasActiveSearchCriteria(resetSnapshot));
        setFacetHasFacesCounts(parseHasFacesFacetCounts(resetPayload.facets));
        setFacetPathHintCounts(toPathHintFacetCounts(resetPayload.facets, resetSnapshot.pathHints));
        setCursorByPage(buildFirstPageCursorMap(resetPayload.hits.cursor));
        return;
      }
      setResults(payload.hits.items);
      setTotalCount(payload.hits.total);
      setPage(snapshot.page);
      setNextCursor(payload.hits.cursor);
      setLastFailedRequest(null);
      setLastSuccessfulHadCriteria(hadCriteria);
      setFacetHasFacesCounts(parseHasFacesFacetCounts(payload.facets));
      setFacetPathHintCounts(toPathHintFacetCounts(payload.facets, snapshot.pathHints));
      setCursorByPage((current) => {
        const pageCursor = snapshot.cursorByPage[snapshot.page];
        const next = { ...current, ...snapshot.cursorByPage, [snapshot.page]: pageCursor ?? null };
        if (payload.hits.cursor === null) {
          delete next[snapshot.page + 1];
        } else {
          next[snapshot.page + 1] = payload.hits.cursor;
        }
        return next;
      });
    } catch (caughtError: unknown) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load search results.";
      setError(message);
      setLastFailedRequest(createSearchSnapshot(snapshot));
      setResults([]);
      setTotalCount(0);
      setNextCursor(null);
      setFacetHasFacesCounts({ true: 0, false: 0 });
      setFacetPathHintCounts(
        snapshot.pathHints.map((value) => ({
          value,
          count: 0
        }))
      );
    } finally {
      setIsLoading(false);
    }
  }

  function requestSearch(overrides: {
    chips?: string[];
    fromDate?: string;
    toDate?: string;
    personNames?: string[];
    locationRadius?: { latitude: number; longitude: number; radius_km: number } | null;
    hasFaces?: boolean | null;
    pathHints?: string[];
    sortDirection?: SortDirection;
    page?: number;
    cursorByPage?: Record<number, string | null>;
    resetToFirstPage?: boolean;
  } = {}) {
    const shouldResetToFirstPage = overrides.resetToFirstPage ?? false;
    const resolvedPage = shouldResetToFirstPage ? 1 : (overrides.page ?? page);
    const resolvedCursorByPage = shouldResetToFirstPage
      ? { 1: null }
      : (overrides.cursorByPage ?? cursorByPage);

    if (shouldResetToFirstPage) {
      setPage(1);
      setCursorByPage({ 1: null });
      setNextCursor(null);
    }

    const snapshot = createSearchSnapshot({
      chips: overrides.chips ?? queryChips,
      fromDate: overrides.fromDate ?? fromDate,
      toDate: overrides.toDate ?? toDate,
      personNames: overrides.personNames ?? selectedPersonNames,
      locationRadius:
        overrides.locationRadius === undefined ? locationRadiusFilter : overrides.locationRadius,
      hasFaces: overrides.hasFaces === undefined ? hasFacesFilter : overrides.hasFaces,
      pathHints: overrides.pathHints ?? pathHintFilters,
      sortDirection: overrides.sortDirection ?? sortDirection,
      page: resolvedPage,
      cursorByPage: resolvedCursorByPage
    });

    void runSearch(snapshot);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (dateRangeError || locationError) {
      return;
    }

    const trimmed = draftQuery.trim();
    if (
      !trimmed &&
      !hasActiveDateFilter &&
      !hasActivePersonFilter &&
      !hasActiveLocationFilter &&
      !hasActiveHasFacesFilter &&
      !hasActivePathHintFilter
    ) {
      return;
    }

    const nextChips = trimmed ? [...queryChips, trimmed] : queryChips;
    if (trimmed) {
      setQueryChips(nextChips);
      setDraftQuery("");
    }

    requestSearch({ chips: nextChips, resetToFirstPage: true });
  }

  function handleDismissChip(indexToRemove: number) {
    const nextChips = queryChips.filter((_, index) => index !== indexToRemove);
    setQueryChips(nextChips);
    requestSearch({ chips: nextChips, resetToFirstPage: true });
  }

  function handleClearFromDate() {
    setFromDate("");
    requestSearch({ fromDate: "", resetToFirstPage: true });
  }

  function handleClearToDate() {
    setToDate("");
    requestSearch({ toDate: "", resetToFirstPage: true });
  }

  function handleAddPersonByName(displayName: string) {
    if (selectedPersonNames.includes(displayName)) {
      setPersonDraft("");
      setPersonMessage(null);
      return;
    }

    setSelectedPersonNames((current) => [...current, displayName]);
    setPersonDraft("");
    setPersonMessage(null);
  }

  function handleAddPersonFilter() {
    const trimmed = personDraft.trim();
    if (!trimmed) {
      return;
    }

    if (matchingPeople.length === 0) {
      setPersonMessage(`No people match "${trimmed}". Search still works without this filter.`);
      return;
    }

    if (matchingPeople.length > 1) {
      setPersonMessage(`Multiple people match "${trimmed}". Select one from suggestions.`);
      return;
    }

    handleAddPersonByName(matchingPeople[0].display_name);
  }

  function handleRemovePersonFilter(displayName: string) {
    const nextNames = selectedPersonNames.filter((name) => name !== displayName);
    setSelectedPersonNames(nextNames);
    setPersonMessage(null);
    requestSearch({ personNames: nextNames, resetToFirstPage: true });
  }

  function handleMapLocationChange(location: LocationRadiusValue) {
    setLatitudeDraft(String(location.latitude));
    setLongitudeDraft(String(location.longitude));
    setRadiusDraft(String(Number(location.radiusKm.toFixed(3))));
    setMapMessage(null);
  }

  function handleClearLocationFilter() {
    setLatitudeDraft("");
    setLongitudeDraft("");
    setRadiusDraft("");
    requestSearch({ locationRadius: null, resetToFirstPage: true });
  }

  function handleToggleHasFacesFilter(nextValue: boolean) {
    const resolvedValue = hasFacesFilter === nextValue ? null : nextValue;
    setHasFacesFilter(resolvedValue);
    requestSearch({ hasFaces: resolvedValue, resetToFirstPage: true });
  }

  function handleClearHasFacesFilter() {
    if (hasFacesFilter === null) {
      return;
    }

    setHasFacesFilter(null);
    requestSearch({ hasFaces: null, resetToFirstPage: true });
  }

  function handleTogglePathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.includes(pathHint)
      ? pathHintFilters.filter((hint) => hint !== pathHint)
      : normalizePathHintFilters([...pathHintFilters, pathHint]);

    setPathHintFilters(nextHints);
    requestSearch({ pathHints: nextHints, resetToFirstPage: true });
  }

  function handleClearPathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.filter((hint) => hint !== pathHint);
    if (nextHints.length === pathHintFilters.length) {
      return;
    }

    setPathHintFilters(nextHints);
    requestSearch({ pathHints: nextHints, resetToFirstPage: true });
  }

  function handleClearAllPathHints() {
    if (pathHintFilters.length === 0) {
      return;
    }

    setPathHintFilters([]);
    requestSearch({ pathHints: [], resetToFirstPage: true });
  }

  function handleSortDirectionChange(nextDirection: SortDirection) {
    setSortDirection(nextDirection);
    if (!hasRequested) {
      return;
    }

    requestSearch({
      sortDirection: nextDirection,
      resetToFirstPage: true
    });
  }

  function handlePreviousPage() {
    if (isLoading || page <= 1) {
      return;
    }

    requestSearch({
      page: page - 1
    });
  }

  function handleNextPage() {
    if (isLoading || nextCursor === null) {
      return;
    }

    const nextPage = page + 1;
    requestSearch({
      page: nextPage,
      cursorByPage: {
        ...cursorByPage,
        [nextPage]: nextCursor
      }
    });
  }

  function handleRetry() {
    if (lastFailedRequest) {
      void runSearch(lastFailedRequest);
      return;
    }
    requestSearch();
  }

  const resultViewState = useMemo(() => {
    if (isLoading) {
      return "loading";
    }
    if (error) {
      return "error";
    }
    if (!hasRequested) {
      return "idle";
    }
    if (results.length > 0) {
      return "results";
    }
    return lastSuccessfulHadCriteria ? "no_match" : "empty";
  }, [error, hasRequested, isLoading, lastSuccessfulHadCriteria, results.length]);

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return `Loading page ${page}…`;
    }

    if (error) {
      return "Search results unavailable.";
    }

    if (!hasRequested) {
      return "Submit a phrase to search the catalog.";
    }

    return `Showing ${results.length} of ${totalCount} photos`;
  }, [error, hasRequested, isLoading, results.length, totalCount]);

  const canGoPrevious = hasRequested && page > 1 && !isLoading;
  const canGoNext = hasRequested && nextCursor !== null && !isLoading;

  return (
    <section aria-labelledby="page-title" className="page search-page">
      <div className="search-header">
        <div>
          <h1 id="page-title">Search</h1>
          <p>Tokenized phrase chips and inclusive date range filters with deterministic request state.</p>
        </div>
        <div className="search-controls" role="group" aria-label="Search controls">
          <label className="search-sort-control">
            Sort order
            <select
              aria-label="Sort order"
              value={sortDirection}
              onChange={(event) =>
                handleSortDirectionChange(event.target.value === "asc" ? "asc" : "desc")
              }
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </label>
          <div className="search-pagination" aria-label="Pagination controls">
            <button
              type="button"
              onClick={handlePreviousPage}
              disabled={!canGoPrevious}
              aria-label="Previous page"
            >
              Previous
            </button>
            <p className="search-page-indicator">Page {page}</p>
            <button
              type="button"
              onClick={handleNextPage}
              disabled={!canGoNext}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <form className="search-query-form" onSubmit={handleSubmit}>
        <label htmlFor="search-query-input">Search query</label>
        <div className="search-query-row">
          <input
            id="search-query-input"
            type="text"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            aria-describedby="search-query-summary"
          />
          <button type="submit">Search</button>
        </div>
        <div className="search-date-row">
          <label htmlFor="search-date-from">From date</label>
          <input
            id="search-date-from"
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            aria-describedby="search-query-summary search-date-validation"
          />
          <label htmlFor="search-date-to">To date</label>
          <input
            id="search-date-to"
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
            aria-describedby="search-query-summary search-date-validation"
          />
        </div>
        <div className="search-person-row">
          <label htmlFor="search-person-input">Person filter</label>
          <div className="search-person-input-row">
            <input
              id="search-person-input"
              type="text"
              value={personDraft}
              onChange={(event) => setPersonDraft(event.target.value)}
              aria-describedby="search-query-summary search-person-validation"
            />
            <button type="button" onClick={handleAddPersonFilter}>
              Add person filter
            </button>
          </div>
        </div>
        <div className="search-location-panel">
          <p className="search-filter-section-label">Location radius</p>
          <div className="search-location-row">
            <label htmlFor="search-location-latitude">Latitude</label>
            <input
              id="search-location-latitude"
              type="text"
              inputMode="decimal"
              value={latitudeDraft}
              onChange={(event) => setLatitudeDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
            <label htmlFor="search-location-longitude">Longitude</label>
            <input
              id="search-location-longitude"
              type="text"
              inputMode="decimal"
              value={longitudeDraft}
              onChange={(event) => setLongitudeDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
            <label htmlFor="search-location-radius">Radius (km)</label>
            <input
              id="search-location-radius"
              type="text"
              inputMode="decimal"
              value={radiusDraft}
              onChange={(event) => setRadiusDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
          </div>
          <LocationRadiusPicker
            value={
              locationRadiusFilter
                ? {
                    latitude: locationRadiusFilter.latitude,
                    longitude: locationRadiusFilter.longitude,
                    radiusKm: locationRadiusFilter.radius_km
                  }
                : null
            }
            onChange={handleMapLocationChange}
            onMapError={setMapMessage}
          />
        </div>
        <FacetFilterPanel
          hasFacesFilter={hasFacesFilter}
          pathHintFilters={pathHintFilters}
          hasFacesCounts={facetHasFacesCounts}
          pathHintCounts={facetPathHintCounts}
          onToggleHasFaces={handleToggleHasFacesFilter}
          onClearHasFaces={handleClearHasFacesFilter}
          onTogglePathHint={handleTogglePathHintFilter}
          onClearAllPathHints={handleClearAllPathHints}
        />
        {dateRangeError ? (
          <p id="search-date-validation" className="search-validation-message" role="alert">
            {dateRangeError}
          </p>
        ) : null}
        {locationError ? (
          <p id="search-location-validation" className="search-validation-message" role="alert">
            {locationError}
          </p>
        ) : null}
        {personMessage ? (
          <p id="search-person-validation" className="search-validation-message" role="status">
            {personMessage}
          </p>
        ) : null}
        {mapMessage ? (
          <p className="search-map-message" role="status">
            {mapMessage}
          </p>
        ) : null}
        {personMessage?.startsWith("Multiple people match") && matchingPeople.length > 0 ? (
          <ul className="search-person-suggestion-list" aria-label="Person suggestions">
            {matchingPeople.map((person) => (
              <li key={person.person_id}>
                <button
                  type="button"
                  className="search-person-suggestion"
                  onClick={() => handleAddPersonByName(person.display_name)}
                >
                  {person.display_name}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </form>

      {queryChips.length > 0 ||
      hasActiveDateFilter ||
      hasActivePersonFilter ||
      hasActiveLocationFilter ||
      hasActiveHasFacesFilter ||
      hasActivePathHintFilter ? (
        <ul className="search-chip-list" aria-label="Active search filters">
          {locationRadiusFilter ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove ${formatLocationChipLabel({
                  latitude: locationRadiusFilter.latitude,
                  longitude: locationRadiusFilter.longitude,
                  radiusKm: locationRadiusFilter.radius_km
                })}`}
                onClick={handleClearLocationFilter}
              >
                {formatLocationChipLabel({
                  latitude: locationRadiusFilter.latitude,
                  longitude: locationRadiusFilter.longitude,
                  radiusKm: locationRadiusFilter.radius_km
                })}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
          {selectedPersonNames.map((displayName) => (
            <li key={displayName}>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove person ${displayName}`}
                onClick={() => handleRemovePersonFilter(displayName)}
              >
                person: {displayName}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ))}
          {hasFacesFilter !== null ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove has faces filter ${hasFacesFilter ? "with faces" : "without faces"}`}
                onClick={handleClearHasFacesFilter}
              >
                has faces: {hasFacesFilter ? "yes" : "no"}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
          {pathHintFilters.map((pathHint) => (
            <li key={pathHint}>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove path hint ${pathHint}`}
                onClick={() => handleClearPathHintFilter(pathHint)}
              >
                path hint: {pathHint}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ))}
          {fromDate ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove from date ${fromDate}`}
                onClick={handleClearFromDate}
              >
                from: {fromDate}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
          {toDate ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove to date ${toDate}`}
                onClick={handleClearToDate}
              >
                to: {toDate}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
          {queryChips.map((chip, index) => (
            <li key={`${chip}-${index}`}>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove query ${chip}`}
                onClick={() => handleDismissChip(index)}
              >
                {chip}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <p id="search-query-summary" className="search-summary" aria-live="polite">
        {summaryLabel}
      </p>
      {paginationMessage ? (
        <p className="search-pagination-message" role="status">
          {paginationMessage}
        </p>
      ) : null}

      {resultViewState === "loading" ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading search workflow.
        </div>
      ) : null}

      {resultViewState === "error" ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load Search</h2>
          <p>{error}</p>
          <button type="button" onClick={handleRetry}>
            Retry
          </button>
        </div>
      ) : null}

      {resultViewState === "empty" ? (
        <div className="feedback-panel">
          <p>No photos are available in the catalog yet.</p>
        </div>
      ) : null}

      {resultViewState === "no_match" ? (
        <div className="feedback-panel">
          <p>No matching photos for the active query.</p>
        </div>
      ) : null}

      {resultViewState === "results" ? (
        <ol className="search-results" aria-label="Search results">
          {results.map((photo) => (
            <li key={photo.photo_id}>
              <h2>{photo.photo_id}</h2>
              <p className="search-result-path" title={photo.path}>
                {photo.path}
              </p>
            </li>
          ))}
        </ol>
      ) : null}

      <p className="search-serialized-query" aria-live="off">
        Active query: {serializedQuery || "(none)"} | Date range:{" "}
        {fromDate || toDate ? `${fromDate || "(open)"} to ${toDate || "(open)"}` : "(none)"}
        {" | People: "}
        {selectedPersonNames.length > 0 ? selectedPersonNames.join(", ") : "(none)"}
        {" | Location: "}
        {locationRadiusFilter
          ? `${locationRadiusFilter.latitude.toFixed(4)}, ${locationRadiusFilter.longitude.toFixed(4)} (${locationRadiusFilter.radius_km.toFixed(1)} km)`
          : "(none)"}
        {" | Has faces: "}
        {hasFacesFilter === null ? "(none)" : hasFacesFilter ? "true" : "false"}
        {" | Path hints: "}
        {pathHintFilters.length > 0 ? pathHintFilters.join(", ") : "(none)"}
      </p>
    </section>
  );
}

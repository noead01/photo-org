import { FormEvent, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FeedbackSurface } from "../app/feedback/FeedbackSurface";
import type {
  FeedbackViewState,
  NotificationEntry
} from "../app/feedback/feedbackTypes";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../app/ingestStatus";
import { resolveInitialSessionIdentity } from "../session/sessionIdentity";
import { PhotoResultIdentity } from "./library/PhotoResultIdentity";
import { LibraryActionBar } from "./library/LibraryActionBar";
import { resolveLibraryActionState } from "./library/libraryActionBarState";
import {
  createLibrarySelectionState,
  formatSelectionScopeLabel,
  librarySelectionReducer,
  parseLibrarySelectionRouteState,
  resolveSelectionScopeCount,
  serializeLibrarySelectionState
} from "./library/librarySelection";
import { INVALID_PAGE_MESSAGE, updateCursorByPage } from "./library/pagination";
import { isLibraryActionConflictActive } from "./library/operationsActivity";
import { useRouteRequestState } from "./library/requestLifecycle";
import {
  dedupeTrimmedValues,
  parseNullableBooleanParam,
  parsePositiveIntParam
} from "./library/urlSerialization";
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
import { LocationRadiusPicker } from "./search/LocationRadiusPicker";
import type { LocationRadiusValue } from "./search/types";

type SortDirection = "asc" | "desc";

type LibraryPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
  people?: string[];
  faces?: Array<{ person_id: string | null }>;
  thumbnail?: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
  original?: {
    is_available: boolean;
    availability_state: string;
    last_failure_reason: string | null;
  } | null;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    items: LibraryPhoto[];
    cursor: string | null;
  };
  facets?: SearchFacetPayload;
};

type PersonRecord = {
  person_id: string;
  display_name: string;
};

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

const PAGE_LIMIT = 24;
const LIBRARY_FILTER_FINGERPRINT = "library:route";
const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

function formatShotTimestamp(shotTs: string | null): string {
  if (!shotTs) {
    return "Unknown capture time";
  }

  const timestamp = Date.parse(shotTs);
  if (Number.isNaN(timestamp)) {
    return shotTs;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC"
  }).format(timestamp);
}

function formatFilesize(filesize: number): string {
  if (filesize < 1024) {
    return `${filesize} B`;
  }

  const kb = filesize / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
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

function parseLibraryUrlState(search: string): SearchUrlState {
  const params = new URLSearchParams(search);
  const queryChips = dedupeTrimmedValues(params.getAll("query"));

  const fromCandidate = (params.get("from") ?? "").trim();
  const toCandidate = (params.get("to") ?? "").trim();
  const fromDate = isValidIsoDate(fromCandidate) ? fromCandidate : "";
  const toDate = isValidIsoDate(toCandidate) ? toCandidate : "";

  const selectedPersonNames = dedupeTrimmedValues(params.getAll("person"));
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
    latitudeDraft: locationDrafts.latitudeDraft,
    longitudeDraft: locationDrafts.longitudeDraft,
    radiusDraft: locationDrafts.radiusDraft,
    locationRadius,
    hasFacesFilter,
    pathHintFilters
  };
}

function buildLibraryUrlQuery(state: {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null;
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

async function fetchLibraryPage(
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
      ...(query ? { q: query } : {}),
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

async function fetchOperationsActivityConflictState(): Promise<boolean> {
  const response = await fetch("/api/v1/operations/activity");
  if (!response.ok) {
    return false;
  }

  const payload = (await response.json()) as unknown;
  return isLibraryActionConflictActive(payload);
}

export function LibraryRoutePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const requestedPage = parsePositiveIntParam(location.search, "page");
  const suppressNextUrlStateSyncRef = useRef(false);
  const applyingParsedUrlStateRef = useRef(false);
  const parsedUrlState = useMemo(() => parseLibraryUrlState(location.search), [location.search]);

  const headingRef = useRef<HTMLHeadingElement | null>(null);

  const [queryInput, setQueryInput] = useState("");
  const [committedQuery, setCommittedQuery] = useState("");
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

  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [cursorByPage, setCursorByPage] = useState<Record<number, string | null>>({ 1: null });
  const [photos, setPhotos] = useState<LibraryPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [hasConflictingJob, setHasConflictingJob] = useState(false);
  const [selectionState, dispatchSelection] = useReducer(
    librarySelectionReducer,
    parseLibrarySelectionRouteState(
      isRecord(location.state)
        ? location.state.librarySelection ?? location.state.browseSelection
        : undefined
    ),
    createLibrarySelectionState
  );
  const {
    isLoading,
    error,
    reloadToken,
    beginRequest,
    completeRequest,
    failRequest,
    requestRetry
  } = useRouteRequestState();

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

  const selectionRouteState = useMemo(
    () => serializeLibrarySelectionState(selectionState),
    [selectionState]
  );

  const cursorForPage = cursorByPage[requestedPage];

  function setPage(pageNumber: number, replace = false) {
    const nextParams = new URLSearchParams(location.search);
    if (pageNumber <= 1) {
      nextParams.delete("page");
    } else {
      nextParams.set("page", String(pageNumber));
    }

    const nextSearch = nextParams.toString();
    const nextTarget = `${location.pathname}${nextSearch ? `?${nextSearch}` : ""}`;
    const currentTarget = `${location.pathname}${location.search}`;

    if (nextTarget !== currentTarget) {
      navigate(nextTarget, { replace });
    }
  }

  function pushWarning(message: string) {
    setNotifications((current) => [
      {
        id: "library-warning",
        tone: "warning",
        message
      },
      ...current.filter((entry) => entry.id !== "library-warning")
    ]);
  }

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
          setPeopleDirectory([]);
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
    const parsedQuery = parsedUrlState.queryChips.join(" ");
    setQueryInput(parsedQuery);
    setCommittedQuery(parsedQuery);
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
    setFacetPathHintCounts(
      parsedUrlState.pathHintFilters.map((value) => ({
        value,
        count: 0
      }))
    );

    setSortDirection("desc");
    setCursorByPage({ 1: null });
    setNextCursor(null);
    setPhotos([]);
    setTotalCount(0);
  }, [parsedUrlState]);

  useEffect(() => {
    if (applyingParsedUrlStateRef.current) {
      applyingParsedUrlStateRef.current = false;
      return;
    }

    const nextQuery = buildLibraryUrlQuery({
      queryChips: committedQuery ? [committedQuery] : [],
      fromDate,
      toDate,
      selectedPersonNames,
      locationRadius: locationRadiusFilter,
      hasFacesFilter,
      pathHintFilters,
      page: requestedPage
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
    committedQuery,
    fromDate,
    hasFacesFilter,
    location.pathname,
    location.search,
    locationRadiusFilter,
    navigate,
    pathHintFilters,
    requestedPage,
    selectedPersonNames,
    toDate
  ]);

  useEffect(() => {
    dispatchSelection({
      type: "filtersChanged",
      activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
    });
  }, []);

  useEffect(() => {
    const currentRouteSelection = parseLibrarySelectionRouteState(
      isRecord(location.state)
        ? location.state.librarySelection ?? location.state.browseSelection
        : undefined
    );

    if (areSelectionRouteStatesEqual(currentRouteSelection, selectionRouteState)) {
      return;
    }

    const routeState = isRecord(location.state) ? location.state : {};
    navigate(
      {
        pathname: location.pathname,
        search: location.search
      },
      {
        replace: true,
        state: {
          ...routeState,
          librarySelection: selectionRouteState
        }
      }
    );
  }, [location.pathname, location.search, location.state, navigate, selectionRouteState]);

  useEffect(() => {
    if (requestedPage > 1 && cursorForPage === undefined) {
      pushWarning(INVALID_PAGE_MESSAGE);
      setPage(1, true);
      return;
    }

    if (dateRangeError || locationError) {
      setPhotos([]);
      setTotalCount(0);
      setNextCursor(null);
      return;
    }

    const controller = new AbortController();
    beginRequest();

    fetchLibraryPage(
      committedQuery,
      fromDate,
      toDate,
      selectedPersonNames,
      locationRadiusFilter,
      hasFacesFilter,
      pathHintFilters,
      sortDirection,
      cursorForPage ?? null
    )
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }

        if (requestedPage > 1 && payload.hits.items.length === 0) {
          pushWarning(INVALID_PAGE_MESSAGE);
          setPage(1, true);
          return;
        }

        setPhotos(payload.hits.items);
        setTotalCount(payload.hits.total);
        setNextCursor(payload.hits.cursor);
        setFacetHasFacesCounts(parseHasFacesFacetCounts(payload.facets));
        setFacetPathHintCounts(toPathHintFacetCounts(payload.facets, pathHintFilters));
        setCursorByPage((current) =>
          updateCursorByPage(current, requestedPage, cursorForPage ?? null, payload.hits.cursor)
        );
        completeRequest();
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        failRequest(caughtError, "Could not load library results.");
      });

    return () => {
      controller.abort();
    };
  }, [
    committedQuery,
    cursorForPage,
    dateRangeError,
    fromDate,
    hasFacesFilter,
    locationError,
    locationRadiusFilter,
    pathHintFilters,
    reloadToken,
    requestedPage,
    selectedPersonNames,
    sortDirection,
    toDate
  ]);

  useEffect(() => {
    let isMounted = true;
    fetchOperationsActivityConflictState()
      .then((isConflictActive) => {
        if (isMounted) {
          setHasConflictingJob(isConflictActive);
        }
      })
      .catch(() => {
        if (isMounted) {
          setHasConflictingJob(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [reloadToken]);

  const canGoPrevious = requestedPage > 1 && !isLoading;
  const canGoNext = nextCursor !== null && !isLoading;
  const feedbackViewState: FeedbackViewState = isLoading
    ? "loading"
    : error
      ? "error"
      : "ready";

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return `Loading page ${requestedPage}…`;
    }
    if (error) {
      return "Library results unavailable.";
    }
    return `Showing ${photos.length} of ${totalCount} photos`;
  }, [error, isLoading, photos.length, requestedPage, totalCount]);

  const activeScopeCount = resolveSelectionScopeCount(selectionState, {
    currentPageCount: photos.length,
    totalFilteredCount: totalCount
  });
  const sessionIdentity = resolveInitialSessionIdentity();
  const actionState = resolveLibraryActionState({
    selectionCount: activeScopeCount,
    canAddToAlbum: sessionIdentity?.capabilities.addToAlbum ?? false,
    canExport: sessionIdentity?.capabilities.export ?? false,
    hasConflictingJob
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (dateRangeError || locationError) {
      return;
    }

    setCommittedQuery(queryInput.trim());
    setCursorByPage({ 1: null });
    setNextCursor(null);
    setPage(1);
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
    setCursorByPage({ 1: null });
    setPage(1);
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
    setSelectedPersonNames((current) => current.filter((name) => name !== displayName));
    setPersonMessage(null);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleMapLocationChange(locationValue: LocationRadiusValue) {
    setLatitudeDraft(String(locationValue.latitude));
    setLongitudeDraft(String(locationValue.longitude));
    setRadiusDraft(String(Number(locationValue.radiusKm.toFixed(3))));
    setMapMessage(null);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearLocationFilter() {
    setLatitudeDraft("");
    setLongitudeDraft("");
    setRadiusDraft("");
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleToggleHasFacesFilter(nextValue: boolean) {
    const resolvedValue = hasFacesFilter === nextValue ? null : nextValue;
    setHasFacesFilter(resolvedValue);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearHasFacesFilter() {
    if (hasFacesFilter === null) {
      return;
    }

    setHasFacesFilter(null);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleTogglePathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.includes(pathHint)
      ? pathHintFilters.filter((hint) => hint !== pathHint)
      : normalizePathHintFilters([...pathHintFilters, pathHint]);

    setPathHintFilters(nextHints);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearPathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.filter((hint) => hint !== pathHint);
    if (nextHints.length === pathHintFilters.length) {
      return;
    }

    setPathHintFilters(nextHints);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearAllPathHints() {
    if (pathHintFilters.length === 0) {
      return;
    }

    setPathHintFilters([]);
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearFromDate() {
    setFromDate("");
    setCursorByPage({ 1: null });
    setPage(1);
  }

  function handleClearToDate() {
    setToDate("");
    setCursorByPage({ 1: null });
    setPage(1);
  }

  return (
    <section aria-labelledby="page-title" className="page browse-page">
      <div className="browse-header">
        <div>
          <h1 id="page-title" ref={headingRef} tabIndex={-1}>
            Library
          </h1>
          <p>Unified library workflow for search, scope, and action surfaces.</p>
        </div>
        <div className="browse-controls" role="group" aria-label="Library controls">
          <label className="browse-sort-control">
            Sort order
            <select
              aria-label="Sort order"
              value={sortDirection}
              onChange={(event) => {
                const nextDirection = event.target.value === "asc" ? "asc" : "desc";
                setSortDirection(nextDirection);
                setCursorByPage({ 1: null });
                setPage(1);
              }}
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </label>
          <div className="browse-pagination" aria-label="Pagination controls">
            <button
              type="button"
              onClick={() => setPage(requestedPage - 1)}
              disabled={!canGoPrevious}
              aria-label="Previous page"
            >
              Previous
            </button>
            <p className="browse-page-indicator">Page {requestedPage}</p>
            <button
              type="button"
              onClick={() => setPage(requestedPage + 1)}
              disabled={!canGoNext}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <form className="search-query-form" onSubmit={handleSubmit}>
        <div className="search-query-row">
          <input
            aria-label="Search query"
            value={queryInput}
            onChange={(event) => setQueryInput(event.target.value)}
          />
          <button type="submit">Search</button>
        </div>

        <div className="search-date-row">
          <label htmlFor="search-date-from">From date</label>
          <input
            id="search-date-from"
            type="date"
            value={fromDate}
            onChange={(event) => {
              setFromDate(event.target.value);
              setCursorByPage({ 1: null });
              setPage(1);
            }}
            aria-describedby="search-date-validation"
          />
          <label htmlFor="search-date-to">To date</label>
          <input
            id="search-date-to"
            type="date"
            value={toDate}
            onChange={(event) => {
              setToDate(event.target.value);
              setCursorByPage({ 1: null });
              setPage(1);
            }}
            aria-describedby="search-date-validation"
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
              aria-describedby="search-person-validation"
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
              onChange={(event) => {
                setLatitudeDraft(event.target.value);
                setCursorByPage({ 1: null });
                setPage(1);
              }}
              aria-describedby="search-location-validation"
            />
            <label htmlFor="search-location-longitude">Longitude</label>
            <input
              id="search-location-longitude"
              type="text"
              inputMode="decimal"
              value={longitudeDraft}
              onChange={(event) => {
                setLongitudeDraft(event.target.value);
                setCursorByPage({ 1: null });
                setPage(1);
              }}
              aria-describedby="search-location-validation"
            />
            <label htmlFor="search-location-radius">Radius (km)</label>
            <input
              id="search-location-radius"
              type="text"
              inputMode="decimal"
              value={radiusDraft}
              onChange={(event) => {
                setRadiusDraft(event.target.value);
                setCursorByPage({ 1: null });
                setPage(1);
              }}
              aria-describedby="search-location-validation"
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

      {committedQuery ||
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
          {committedQuery ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove query ${committedQuery}`}
                onClick={() => {
                  setCommittedQuery("");
                  setQueryInput("");
                  setCursorByPage({ 1: null });
                  setPage(1);
                }}
              >
                {committedQuery}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
        </ul>
      ) : null}

      <p className="browse-summary" aria-live="polite">{summaryLabel}</p>

      <section className="browse-selection-panel" aria-label="Library selection controls">
        <fieldset className="browse-selection-scope-group">
          <legend>Selection scope</legend>
          <label>
            <input
              type="radio"
              name="library-selection-scope"
              value="selected"
              checked={selectionState.scope === "selected"}
              onChange={() =>
                dispatchSelection({
                  type: "setScope",
                  scope: "selected",
                  activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
                })
              }
            />
            Selected
          </label>
          <label>
            <input
              type="radio"
              name="library-selection-scope"
              value="page"
              checked={selectionState.scope === "page"}
              onChange={() =>
                dispatchSelection({
                  type: "setScope",
                  scope: "page",
                  activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
                })
              }
            />
            This page
          </label>
          <label>
            <input
              type="radio"
              name="library-selection-scope"
              value="allFiltered"
              checked={selectionState.scope === "allFiltered"}
              onChange={() =>
                dispatchSelection({
                  type: "setScope",
                  scope: "allFiltered",
                  activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
                })
              }
            />
            All filtered
          </label>
        </fieldset>
        <p className="browse-selection-summary" aria-live="polite">
          {`${formatSelectionScopeLabel(selectionState.scope)} scope: ${activeScopeCount} photo${activeScopeCount === 1 ? "" : "s"}`}
        </p>
        <button
          type="button"
          onClick={() => dispatchSelection({ type: "clearExplicitSelection" })}
          disabled={selectionState.selectedPhotoIds.size === 0}
        >
          Clear selected
        </button>
      </section>

      <LibraryActionBar
        selectionCount={activeScopeCount}
        actionState={actionState}
        onAction={(action) => {
          setNotifications((current) => [
            {
              id: `library-action-${action}`,
              tone: "warning",
              message: `${action === "addToAlbum" ? "Add to album" : "Export"} is not implemented yet.`
            },
            ...current
          ]);
        }}
      />

      <section className="status-legend" aria-label="Ingest status legend">
        <h2>Ingest status legend</h2>
        <ul>
          {INGEST_STATUS_LEGEND.map((entry) => (
            <li key={entry.tone}>
              <span className={`ingest-status-badge is-${entry.tone}`}>{entry.label}</span>
              <span>{entry.description}</span>
            </li>
          ))}
        </ul>
      </section>

      <FeedbackSurface
        viewState={feedbackViewState}
        loadingLabel="Loading library workflow."
        error={error ? { title: "Could not load Library", message: error } : null}
        onRetry={requestRetry}
        notifications={notifications}
        onDismissNotification={(id) => {
          setNotifications((current) => current.filter((entry) => entry.id !== id));
        }}
      >
        {!error && !isLoading && photos.length === 0 ? (
          <div className="feedback-panel">
            <p>No photos available for this page.</p>
          </div>
        ) : null}

        {!error && !isLoading && photos.length > 0 ? (
          <ol className="browse-grid" aria-label="Photo gallery">
            {photos.map((photo) => {
              const ingestStatus = deriveIngestStatus({
                availabilityState: photo.original?.availability_state ?? null,
                isAvailable: photo.original?.is_available ?? null,
                lastFailureReason: photo.original?.last_failure_reason ?? null,
                hasThumbnail: Boolean(photo.thumbnail)
              });

              return (
                <li key={photo.photo_id} className="browse-card">
                  <p className="browse-ingest-status">
                    <span className={`ingest-status-badge is-${ingestStatus.tone}`}>
                      {ingestStatus.label}
                    </span>
                    <span className="browse-ingest-status-detail">
                      {ingestStatus.description}
                    </span>
                  </p>
                  <label className="browse-card-selection">
                    <input
                      type="checkbox"
                      checked={selectionState.selectedPhotoIds.has(photo.photo_id)}
                      onChange={() =>
                        dispatchSelection({
                          type: "togglePhotoSelection",
                          photoId: photo.photo_id
                        })
                      }
                    />
                    Select photo
                  </label>
                  {photo.thumbnail ? (
                    <img
                      className="browse-thumbnail"
                      src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                      width={photo.thumbnail.width}
                      height={photo.thumbnail.height}
                      alt={`Thumbnail for ${photo.photo_id}`}
                    />
                  ) : (
                    <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                      No preview
                    </div>
                  )}
                  <div className="browse-card-body">
                    <PhotoResultIdentity
                      title={
                        <Link
                          className="browse-photo-link"
                          data-photo-id={photo.photo_id}
                          to={`/library/${photo.photo_id}`}
                          state={{
                            returnToLibrarySearch: location.search,
                            returnFocusPhotoId: photo.photo_id,
                            librarySelection: selectionRouteState
                          }}
                        >
                          {photo.photo_id}
                        </Link>
                      }
                      path={photo.path}
                      pathClassName="browse-path"
                    />
                    <dl>
                      <div>
                        <dt>Captured</dt>
                        <dd>{formatShotTimestamp(photo.shot_ts)}</dd>
                      </div>
                      <div>
                        <dt>Size</dt>
                        <dd>{formatFilesize(photo.filesize)}</dd>
                      </div>
                      <div>
                        <dt>People</dt>
                        <dd>{photo.people?.length ?? 0}</dd>
                      </div>
                      <div>
                        <dt>Original</dt>
                        <dd>{photo.original?.availability_state ?? "unknown"}</dd>
                      </div>
                    </dl>
                  </div>
                </li>
              );
            })}
          </ol>
        ) : null}
      </FeedbackSurface>
    </section>
  );
}

function areSelectionRouteStatesEqual(
  left: ReturnType<typeof parseLibrarySelectionRouteState>,
  right: ReturnType<typeof serializeLibrarySelectionState>
): boolean {
  if (!left) {
    return false;
  }
  if (left.scope !== right.scope) {
    return false;
  }
  if (left.allFilteredFingerprint !== right.allFilteredFingerprint) {
    return false;
  }
  if (left.selectedPhotoIds.length !== right.selectedPhotoIds.length) {
    return false;
  }

  return left.selectedPhotoIds.every((photoId, index) => photoId === right.selectedPhotoIds[index]);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

import { FormEvent, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FeedbackSurface } from "../app/feedback/FeedbackSurface";
import type {
  FeedbackViewState,
  NotificationEntry
} from "../app/feedback/feedbackTypes";
import { resolveInitialSessionIdentity } from "../session/sessionIdentity";
import { LibraryActionBar } from "./library/LibraryActionBar";
import { LibraryActiveFilterChips } from "./library/LibraryActiveFilterChips";
import { fetchLibraryPage, fetchOperationsActivityConflictState, fetchPeopleDirectory } from "./library/libraryRouteApi";
import { LibraryPhotoGrid } from "./library/LibraryPhotoGrid";
import { LibraryRouteHeader } from "./library/LibraryRouteHeader";
import { LibrarySearchForm } from "./library/LibrarySearchForm";
import { LibrarySelectionPanel } from "./library/LibrarySelectionPanel";
import { resolveLibraryActionState } from "./library/libraryActionBarState";
import { isFuzzyNameMatch, parseLibraryUrlState, validateDateRange, buildLibraryUrlQuery } from "./library/libraryRouteSearchState";
import {
  createLibrarySelectionState,
  librarySelectionReducer,
  parseLibrarySelectionRouteState,
  resolveSelectionScopeCount,
  serializeLibrarySelectionState
} from "./library/librarySelection";
import { INVALID_PAGE_MESSAGE, updateCursorByPage } from "./library/pagination";
import { useRouteRequestState } from "./library/requestLifecycle";
import { parsePositiveIntParam } from "./library/urlSerialization";
import {
  normalizePathHintFilters,
  parseHasFacesFacetCounts,
  toPathHintFacetCounts,
  type FacetCountEntry
} from "./search/facetFilters";
import {
  buildLocationRadiusFilter,
  parseLocationDraft,
  validateLocationDraft
} from "./search/locationFilter";
import type { LocationRadiusValue } from "./search/types";
import type { LibraryPhoto, PersonRecord, SortDirection } from "./library/libraryRouteTypes";

const LIBRARY_FILTER_FINGERPRINT = "library:route";

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
        const payload = await fetchPeopleDirectory();
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
      <LibraryRouteHeader
        headingRef={headingRef}
        sortDirection={sortDirection}
        requestedPage={requestedPage}
        canGoPrevious={canGoPrevious}
        canGoNext={canGoNext}
        onSortDirectionChange={(nextDirection) => {
          setSortDirection(nextDirection);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onPreviousPage={() => setPage(requestedPage - 1)}
        onNextPage={() => setPage(requestedPage + 1)}
      />

      <LibrarySearchForm
        queryInput={queryInput}
        fromDate={fromDate}
        toDate={toDate}
        personDraft={personDraft}
        selectedPersonNames={selectedPersonNames}
        latitudeDraft={latitudeDraft}
        longitudeDraft={longitudeDraft}
        radiusDraft={radiusDraft}
        locationRadius={
          locationRadiusFilter
            ? {
                latitude: locationRadiusFilter.latitude,
                longitude: locationRadiusFilter.longitude,
                radiusKm: locationRadiusFilter.radius_km
              }
            : null
        }
        hasFacesFilter={hasFacesFilter}
        pathHintFilters={pathHintFilters}
        facetHasFacesCounts={facetHasFacesCounts}
        facetPathHintCounts={facetPathHintCounts}
        dateRangeError={dateRangeError}
        locationError={locationError}
        personMessage={personMessage}
        mapMessage={mapMessage}
        matchingPeople={matchingPeople}
        onSubmit={handleSubmit}
        onQueryInputChange={setQueryInput}
        onFromDateChange={(value) => {
          setFromDate(value);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onToDateChange={(value) => {
          setToDate(value);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onPersonDraftChange={setPersonDraft}
        onAddPersonFilter={handleAddPersonFilter}
        onAddPersonByName={handleAddPersonByName}
        onLatitudeDraftChange={(value) => {
          setLatitudeDraft(value);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onLongitudeDraftChange={(value) => {
          setLongitudeDraft(value);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onRadiusDraftChange={(value) => {
          setRadiusDraft(value);
          setCursorByPage({ 1: null });
          setPage(1);
        }}
        onMapLocationChange={handleMapLocationChange}
        onMapError={setMapMessage}
        onToggleHasFacesFilter={handleToggleHasFacesFilter}
        onClearHasFacesFilter={handleClearHasFacesFilter}
        onTogglePathHintFilter={handleTogglePathHintFilter}
        onClearAllPathHints={handleClearAllPathHints}
      />

      <LibraryActiveFilterChips
        committedQuery={committedQuery}
        fromDate={fromDate}
        toDate={toDate}
        selectedPersonNames={selectedPersonNames}
        locationRadius={locationRadiusFilter}
        hasFacesFilter={hasFacesFilter}
        pathHintFilters={pathHintFilters}
        onClearLocationFilter={handleClearLocationFilter}
        onRemovePersonFilter={handleRemovePersonFilter}
        onClearHasFacesFilter={handleClearHasFacesFilter}
        onClearPathHintFilter={handleClearPathHintFilter}
        onClearFromDate={handleClearFromDate}
        onClearToDate={handleClearToDate}
        onClearCommittedQuery={() => {
          setCommittedQuery("");
          setQueryInput("");
          setCursorByPage({ 1: null });
          setPage(1);
        }}
      />

      <p className="browse-summary" aria-live="polite">{summaryLabel}</p>

      <LibrarySelectionPanel
        selectionState={selectionState}
        activeScopeCount={activeScopeCount}
        onSetScope={(scope) =>
          dispatchSelection({
            type: "setScope",
            scope,
            activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
          })
        }
        onClearExplicitSelection={() => dispatchSelection({ type: "clearExplicitSelection" })}
      />

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
          <LibraryPhotoGrid
            photos={photos}
            selectedPhotoIds={selectionState.selectedPhotoIds}
            locationSearch={location.search}
            selectionRouteState={selectionRouteState}
            onToggleSelection={(photoId) =>
              dispatchSelection({
                type: "togglePhotoSelection",
                photoId
              })
            }
          />
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

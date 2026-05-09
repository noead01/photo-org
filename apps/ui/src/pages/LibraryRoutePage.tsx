import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FeedbackSurface } from "../app/feedback/FeedbackSurface";
import type {
  NotificationEntry
} from "../app/feedback/feedbackTypes";
import { resolveInitialSessionIdentity } from "../session/sessionIdentity";
import { LibraryActionBar } from "./library/LibraryActionBar";
import { LibraryActiveFilterChips } from "./library/LibraryActiveFilterChips";
import {
  DEFAULT_SEARCH_PAGE_LIMIT,
  fetchAlbums,
  fetchPeopleDirectory,
  SEARCH_PAGE_LIMIT_OPTIONS,
  type AlbumRecord
} from "./library/libraryRouteApi";
import { AddToAlbumDialog } from "./library/AddToAlbumDialog";
import { LibraryPhotoGrid } from "./library/LibraryPhotoGrid";
import { LibraryRouteHeader } from "./library/LibraryRouteHeader";
import { LibrarySearchForm } from "./library/LibrarySearchForm";
import { LibrarySelectionPanel } from "./library/LibrarySelectionPanel";
import { resolveLibraryActionState } from "./library/libraryActionBarState";
import {
  consumePendingLibraryFocusPhotoId,
  resolveLibraryReturnState,
  type LibraryViewRouteState
} from "./libraryRouteState";
import {
  isFuzzyNameMatch,
  parseLibraryUrlState,
  validateDateRange
} from "./library/libraryRouteSearchState";
import {
  createLibrarySelectionState,
  librarySelectionReducer,
  parseLibrarySelectionRouteState,
  resolveSelectionScopeCount,
  serializeLibrarySelectionState
} from "./library/librarySelection";
import { useRouteRequestState } from "./library/requestLifecycle";
import { parsePositiveIntParam } from "./library/urlSerialization";
import {
  loadLibraryViewState,
  saveLibraryViewState
} from "./library/libraryRouteMemory";
import {
  normalizePathHintFilters,
  type FacetCountEntry
} from "./search/facetFilters";
import {
  buildLocationRadiusFilter,
  parseLocationDraft,
  validateLocationDraft
} from "./search/locationFilter";
import type { LocationRadiusValue } from "./search/types";
import type {
  PersonCertaintyMode,
  PersonRecord,
  SearchUrlState,
  SortDirection
} from "./library/libraryRouteTypes";
import { useLibraryBulkActions } from "./library/useLibraryBulkActions";
import { useLibraryResults } from "./library/useLibraryResults";
import { useLibraryReturnFocus } from "./library/useLibraryReturnFocus";
import { useLibraryRouteStateSync } from "./library/useLibraryRouteStateSync";
import { useLibraryUrlSync } from "./library/useLibraryUrlSync";

const LIBRARY_FILTER_FINGERPRINT = "library:route";
function toEditableAlbumOptions(albums: AlbumRecord[]): Array<{ albumId: string; albumName: string }> {
  return albums
    .filter((album) => album.kind === "editable")
    .map((album) => ({ albumId: album.album_id, albumName: album.name }))
    .sort((left, right) => left.albumName.localeCompare(right.albumName, "en-US"));
}

export function LibraryRoutePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const initialReturnState = resolveLibraryReturnState(location.state);
  const requestedPage = parsePositiveIntParam(location.search, "page");
  const suppressNextUrlStateSyncRef = useRef(false);
  const applyingParsedUrlStateRef = useRef(false);
  const parsedUrlState = useMemo(() => parseLibraryUrlState(location.search), [location.search]);
  const parsedUrlStateSignature = useMemo(
    () =>
      JSON.stringify({
        queryChips: parsedUrlState.queryChips,
        fromDate: parsedUrlState.fromDate,
        toDate: parsedUrlState.toDate,
        sortDirection: parsedUrlState.sortDirection,
        pageSize: parsedUrlState.pageSize,
        selectedPersonNames: parsedUrlState.selectedPersonNames,
        selectedAlbumIds: parsedUrlState.selectedAlbumIds,
        personCertaintyMode: parsedUrlState.personCertaintyMode,
        suggestionConfidenceMinDraft: parsedUrlState.suggestionConfidenceMinDraft,
        latitudeDraft: parsedUrlState.latitudeDraft,
        longitudeDraft: parsedUrlState.longitudeDraft,
        radiusDraft: parsedUrlState.radiusDraft,
        hasFacesFilter: parsedUrlState.hasFacesFilter,
        pathHintFilters: parsedUrlState.pathHintFilters
      }),
    [parsedUrlState]
  );
  const lastAppliedParsedUrlStateSignatureRef = useRef<string | null>(parsedUrlStateSignature);
  const initialStoredViewStateRef = useRef(loadLibraryViewState(location.search));
  const shouldRestoreInitialViewStateRef = useRef(
    Boolean(initialReturnState?.libraryViewState ?? initialStoredViewStateRef.current)
  );

  const headingRef = useRef<HTMLHeadingElement | null>(null);

  const initialCommittedQuery = parsedUrlState.queryChips.join(" ");
  const [queryInput, setQueryInput] = useState(initialCommittedQuery);
  const [committedQuery, setCommittedQuery] = useState(initialCommittedQuery);
  const [fromDate, setFromDate] = useState(parsedUrlState.fromDate);
  const [toDate, setToDate] = useState(parsedUrlState.toDate);
  const [personDraft, setPersonDraft] = useState("");
  const [selectedPersonNames, setSelectedPersonNames] = useState<string[]>(
    parsedUrlState.selectedPersonNames
  );
  const [selectedAlbumIds, setSelectedAlbumIds] = useState<string[]>(
    parsedUrlState.selectedAlbumIds
  );
  const [personCertaintyMode, setPersonCertaintyMode] = useState<PersonCertaintyMode>(
    parsedUrlState.personCertaintyMode
  );
  const [suggestionConfidenceMinDraft, setSuggestionConfidenceMinDraft] = useState(
    parsedUrlState.suggestionConfidenceMinDraft
  );
  const [latitudeDraft, setLatitudeDraft] = useState(parsedUrlState.latitudeDraft);
  const [longitudeDraft, setLongitudeDraft] = useState(parsedUrlState.longitudeDraft);
  const [radiusDraft, setRadiusDraft] = useState(parsedUrlState.radiusDraft);
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const [personMessage, setPersonMessage] = useState<string | null>(null);
  const [mapMessage, setMapMessage] = useState<string | null>(null);
  const [hasFacesFilter, setHasFacesFilter] = useState<boolean | null>(parsedUrlState.hasFacesFilter);
  const [pathHintFilters, setPathHintFilters] = useState<string[]>(parsedUrlState.pathHintFilters);
  const [albumOptions, setAlbumOptions] = useState<Array<{ albumId: string; albumName: string }>>(
    []
  );

  const [sortDirection, setSortDirection] = useState<SortDirection>(
    initialReturnState?.libraryViewState?.sortDirection
      ?? initialStoredViewStateRef.current?.sortDirection
      ?? parsedUrlState.sortDirection
  );
  const [pageSize, setPageSize] = useState(
    initialReturnState?.libraryViewState?.pageSize
      ?? initialStoredViewStateRef.current?.pageSize
      ?? parsedUrlState.pageSize
  );
  const [selectionState, dispatchSelection] = useReducer(
    librarySelectionReducer,
    initialReturnState?.librarySelection ?? null,
    createLibrarySelectionState
  );
  const pendingReturnFocusPhotoIdRef = useRef<string | null>(
    initialReturnState?.restoreFocusPhotoId ?? consumePendingLibraryFocusPhotoId()
  );

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
  const albumNameById = useMemo(() => {
    const next = new Map<string, string>();
    for (const option of albumOptions) {
      next.set(option.albumId, option.albumName);
    }
    return next;
  }, [albumOptions]);

  const libraryViewRouteState = useMemo<LibraryViewRouteState>(
    () => ({
      sortDirection,
      pageSize,
      page: requestedPage
    }),
    [pageSize, requestedPage, sortDirection]
  );
  const {
    photos,
    totalCount,
    facetHasFacesCounts,
    facetPathHintCounts,
    hasConflictingJob,
    isLoading,
    error,
    requestRetry,
    feedbackViewState,
    summaryLabel,
    resetResults,
    setFallbackPathHintCounts
  } = useLibraryResults({
    committedQuery,
    fromDate,
    toDate,
    selectedPersonNames,
    selectedAlbumIds,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    locationRadiusFilter,
    hasFacesFilter,
    pathHintFilters,
    sortDirection,
    requestedPage,
    pageSize,
    dateRangeError,
    locationError
  });
  const applyParsedUrlState = useCallback(
    (nextParsedState: SearchUrlState, shouldApplyViewState: boolean) => {
      const parsedQuery = nextParsedState.queryChips.join(" ");
      setQueryInput(parsedQuery);
      setCommittedQuery(parsedQuery);
      setFromDate(nextParsedState.fromDate);
      setToDate(nextParsedState.toDate);
      setSelectedPersonNames(nextParsedState.selectedPersonNames);
      setSelectedAlbumIds(nextParsedState.selectedAlbumIds);
      setPersonCertaintyMode(nextParsedState.personCertaintyMode);
      setSuggestionConfidenceMinDraft(nextParsedState.suggestionConfidenceMinDraft);
      setPersonDraft("");
      setPersonMessage(null);
      setLatitudeDraft(nextParsedState.latitudeDraft);
      setLongitudeDraft(nextParsedState.longitudeDraft);
      setRadiusDraft(nextParsedState.radiusDraft);
      setMapMessage(null);
      setHasFacesFilter(nextParsedState.hasFacesFilter);
      setPathHintFilters(nextParsedState.pathHintFilters);
      setFallbackPathHintCounts(nextParsedState.pathHintFilters);
      if (shouldApplyViewState) {
        setSortDirection(nextParsedState.sortDirection);
        setPageSize(nextParsedState.pageSize);
      }
      resetResults();
    },
    [resetResults, setFallbackPathHintCounts]
  );
  const { setPage } = useLibraryUrlSync({
    location,
    navigate,
    parsedUrlState,
    parsedUrlStateSignature,
    shouldRestoreInitialViewState: Boolean(initialReturnState?.libraryViewState ?? initialStoredViewStateRef.current),
    committedQuery,
    fromDate,
    toDate,
    selectedPersonNames,
    selectedAlbumIds,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    locationRadiusFilter,
    hasFacesFilter,
    pathHintFilters,
    sortDirection,
    requestedPage,
    pageSize,
    libraryViewRouteState,
    applyParsedUrlState
  });
  const { selectionRouteState } = useLibraryRouteStateSync({
    location,
    navigate,
    selectionState,
    libraryViewRouteState
  });

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
    let isCanceled = false;
    const userId = resolveInitialSessionIdentity()?.userId ?? null;

    async function loadAlbumOptions() {
      try {
        const payload = await fetchAlbums(userId);
        if (isCanceled) {
          return;
        }
        if (!Array.isArray(payload)) {
          setAlbumOptions([]);
          return;
        }
        setAlbumOptions(toEditableAlbumOptions(payload));
      } catch {
        if (!isCanceled) {
          setAlbumOptions([]);
        }
      }
    }

    void loadAlbumOptions();
    return () => {
      isCanceled = true;
    };
  }, []);

  useEffect(() => {
    dispatchSelection({
      type: "filtersChanged",
      activeFilterFingerprint: LIBRARY_FILTER_FINGERPRINT
    });
  }, []);

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(totalCount / pageSize)),
    [totalCount, pageSize]
  );
  const canGoPrevious = requestedPage > 1 && !isLoading;
  const canGoNext = requestedPage < totalPages && !isLoading;
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
  const {
    notifications,
    dismissNotification,
    handleLibraryAction,
    isAddToAlbumDialogOpen,
    addToAlbumKind,
    addToAlbumName,
    addToAlbumPhotoIds,
    showAlbumTypeInfo,
    addToAlbumError,
    isSavingAlbum,
    closeAddToAlbumDialog,
    handleSaveToAlbum,
    setAddToAlbumKind,
    setAddToAlbumName,
    setShowAlbumTypeInfo,
    setAddToAlbumError
  } = useLibraryBulkActions({
    selectionState,
    photos,
    committedQuery,
    fromDate,
    toDate,
    selectedPersonNames,
    selectedAlbumIds,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    locationRadiusFilter,
    hasFacesFilter,
    pathHintFilters,
    sortDirection
  });
  useLibraryReturnFocus({
    headingRef,
    pendingReturnFocusPhotoIdRef,
    isLoading,
    error,
    photos
  });

  function handleSubmit(event: { preventDefault: () => void }) {
    event.preventDefault();
    if (dateRangeError || locationError) {
      return;
    }

    setCommittedQuery(queryInput.trim());
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
    setPage(1);
  }

  function handleMapLocationChange(locationValue: LocationRadiusValue) {
    setLatitudeDraft(String(locationValue.latitude));
    setLongitudeDraft(String(locationValue.longitude));
    setRadiusDraft(String(Number(locationValue.radiusKm.toFixed(3))));
    setMapMessage(null);
    setPage(1);
  }

  function handleClearLocationFilter() {
    setLatitudeDraft("");
    setLongitudeDraft("");
    setRadiusDraft("");
    setPage(1);
  }

  function handleToggleHasFacesFilter(nextValue: boolean) {
    const resolvedValue = hasFacesFilter === nextValue ? null : nextValue;
    setHasFacesFilter(resolvedValue);
    setPage(1);
  }

  function handleClearHasFacesFilter() {
    if (hasFacesFilter === null) {
      return;
    }

    setHasFacesFilter(null);
    setPage(1);
  }

  function handleTogglePathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.includes(pathHint)
      ? pathHintFilters.filter((hint) => hint !== pathHint)
      : normalizePathHintFilters([...pathHintFilters, pathHint]);

    setPathHintFilters(nextHints);
    setPage(1);
  }

  function handleClearPathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.filter((hint) => hint !== pathHint);
    if (nextHints.length === pathHintFilters.length) {
      return;
    }

    setPathHintFilters(nextHints);
    setPage(1);
  }

  function handleClearAllPathHints() {
    if (pathHintFilters.length === 0) {
      return;
    }

    setPathHintFilters([]);
    setPage(1);
  }

  function handleClearFromDate() {
    setFromDate("");
    setPage(1);
  }

  function handleClearToDate() {
    setToDate("");
    setPage(1);
  }

  function handleSelectPage(pageNumber: number) {
    if (isLoading) {
      return;
    }

    const nextPage = Math.max(1, Math.min(pageNumber, totalPages));
    if (nextPage === requestedPage) {
      return;
    }

    setPage(nextPage);
  }

  return (
    <section aria-labelledby="page-title" className="page browse-page">
      <LibraryRouteHeader
        headingRef={headingRef}
        sortDirection={sortDirection}
        requestedPage={requestedPage}
        lastKnownPage={totalPages}
        canGoPrevious={canGoPrevious}
        canGoNext={canGoNext}
        pageSize={pageSize}
        pageSizeOptions={SEARCH_PAGE_LIMIT_OPTIONS}
        onSortDirectionChange={(nextDirection) => {
          setSortDirection(nextDirection);
          setPage(1);
        }}
        onPageSizeChange={(nextPageSize) => {
          if (nextPageSize === pageSize) {
            return;
          }
          const nextPage = resolvePageAfterPageSizeChange(
            requestedPage,
            pageSize,
            nextPageSize
          );
          setPageSize(nextPageSize);
          window.setTimeout(() => {
            setPage(nextPage);
          }, 0);
        }}
        onSelectPage={(pageNumber) => {
          handleSelectPage(pageNumber);
        }}
      />

      <LibrarySearchForm
        queryInput={queryInput}
        fromDate={fromDate}
        toDate={toDate}
        personDraft={personDraft}
        selectedPersonNames={selectedPersonNames}
        selectedAlbumIds={selectedAlbumIds}
        albumFilterOptions={albumOptions}
        personCertaintyMode={personCertaintyMode}
        suggestionConfidenceMinDraft={suggestionConfidenceMinDraft}
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
          setPage(1);
        }}
        onToDateChange={(value) => {
          setToDate(value);
          setPage(1);
        }}
        onPersonDraftChange={setPersonDraft}
        onAddPersonFilter={handleAddPersonFilter}
        onAddPersonByName={handleAddPersonByName}
        onPersonCertaintyModeChange={(value) => {
          setPersonCertaintyMode(value);
          setPage(1);
        }}
        onSuggestionConfidenceMinDraftChange={(value) => {
          setSuggestionConfidenceMinDraft(value);
          setPage(1);
        }}
        onLatitudeDraftChange={(value) => {
          setLatitudeDraft(value);
          setPage(1);
        }}
        onLongitudeDraftChange={(value) => {
          setLongitudeDraft(value);
          setPage(1);
        }}
        onRadiusDraftChange={(value) => {
          setRadiusDraft(value);
          setPage(1);
        }}
        onMapLocationChange={handleMapLocationChange}
        onMapError={setMapMessage}
        onToggleHasFacesFilter={handleToggleHasFacesFilter}
        onClearHasFacesFilter={handleClearHasFacesFilter}
        onToggleAlbumFilter={(albumId) => {
          const nextAlbumIds = selectedAlbumIds.includes(albumId)
            ? selectedAlbumIds.filter((candidate) => candidate !== albumId)
            : [...selectedAlbumIds, albumId];
          setSelectedAlbumIds(nextAlbumIds);
          setPage(1);
        }}
        onClearAllAlbumFilters={() => {
          if (selectedAlbumIds.length === 0) {
            return;
          }
          setSelectedAlbumIds([]);
          setPage(1);
        }}
        onTogglePathHintFilter={handleTogglePathHintFilter}
        onClearAllPathHints={handleClearAllPathHints}
      />

      <LibraryActiveFilterChips
        committedQuery={committedQuery}
        fromDate={fromDate}
        toDate={toDate}
        selectedPersonNames={selectedPersonNames}
        selectedAlbumIds={selectedAlbumIds}
        personCertaintyMode={personCertaintyMode}
        suggestionConfidenceMinDraft={suggestionConfidenceMinDraft}
        locationRadius={locationRadiusFilter}
        hasFacesFilter={hasFacesFilter}
        pathHintFilters={pathHintFilters}
        onClearLocationFilter={handleClearLocationFilter}
        onRemovePersonFilter={handleRemovePersonFilter}
        resolveAlbumLabel={(albumId) => albumNameById.get(albumId) ?? albumId}
        onClearAlbumFilter={(albumId) => {
          const nextAlbumIds = selectedAlbumIds.filter((candidate) => candidate !== albumId);
          if (nextAlbumIds.length === selectedAlbumIds.length) {
            return;
          }
          setSelectedAlbumIds(nextAlbumIds);
          setPage(1);
        }}
        onClearHasFacesFilter={handleClearHasFacesFilter}
        onClearPathHintFilter={handleClearPathHintFilter}
        onClearFromDate={handleClearFromDate}
        onClearToDate={handleClearToDate}
        onClearCommittedQuery={() => {
          setCommittedQuery("");
          setQueryInput("");
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
          void handleLibraryAction(action);
        }}
      />

      <AddToAlbumDialog
        isOpen={isAddToAlbumDialogOpen}
        isSaving={isSavingAlbum}
        photoCount={addToAlbumPhotoIds.length}
        albumKind={addToAlbumKind}
        albumName={addToAlbumName}
        showAlbumTypeInfo={showAlbumTypeInfo}
        error={addToAlbumError}
        onClose={closeAddToAlbumDialog}
        onSubmit={(event) => void handleSaveToAlbum(event)}
        onAlbumKindChange={(kind) => {
          setAddToAlbumKind(kind);
          setAddToAlbumError(null);
        }}
        onAlbumNameChange={(value) => {
          setAddToAlbumName(value);
          setAddToAlbumError(null);
        }}
        onToggleAlbumTypeInfo={() => {
          setShowAlbumTypeInfo((current) => !current);
        }}
      />

      <FeedbackSurface
        viewState={feedbackViewState}
        loadingLabel="Loading library workflow."
        error={error ? { title: "Could not load Library", message: error } : null}
        onRetry={requestRetry}
        notifications={notifications}
        onDismissNotification={dismissNotification}
      >
        {!error && !isLoading && photos.length === 0 ? (
          <div className="feedback-panel">
            <p>No photos available for this page.</p>
          </div>
        ) : null}

        {!error && !isLoading && photos.length > 0 ? (
          <LibraryPhotoGrid
            photos={photos}
            locationSearch={location.search}
            selectionRouteState={selectionRouteState}
            libraryViewRouteState={libraryViewRouteState}
            selectedPhotoIds={selectionState.selectedPhotoIds}
            onTogglePhotoSelection={(photoId) => {
              dispatchSelection({
                type: "togglePhotoSelection",
                photoId
              });
            }}
          />
        ) : null}
      </FeedbackSurface>
    </section>
  );
}

function resolvePageAfterPageSizeChange(
  currentPage: number,
  currentPageSize: number,
  nextPageSize: number
): number {
  const safeCurrentPage = Number.isInteger(currentPage) && currentPage > 0 ? currentPage : 1;
  const safeCurrentPageSize = Number.isInteger(currentPageSize) && currentPageSize > 0
    ? currentPageSize
    : DEFAULT_SEARCH_PAGE_LIMIT;
  const safeNextPageSize = Number.isInteger(nextPageSize) && nextPageSize > 0
    ? nextPageSize
    : DEFAULT_SEARCH_PAGE_LIMIT;
  const firstVisibleIndex = (safeCurrentPage - 1) * safeCurrentPageSize;
  return Math.floor(firstVisibleIndex / safeNextPageSize) + 1;
}

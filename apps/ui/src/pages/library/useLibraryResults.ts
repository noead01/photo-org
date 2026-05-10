import { useEffect, useMemo, useState } from "react";
import type { FeedbackViewState } from "../../app/feedback/feedbackTypes";
import {
  fetchLibraryPage,
  fetchOperationsActivityConflictState,
} from "./libraryRouteApi";
import { parseHasFacesFacetCounts, toPathHintFacetCounts, type FacetCountEntry } from "../search/facetFilters";
import { useRouteRequestState } from "./requestLifecycle";
import type {
  LibraryLocationRadius,
  LibraryPhoto,
  PersonCertaintyMode,
  SortDirection,
} from "./libraryRouteTypes";

interface UseLibraryResultsArgs {
  committedQuery: string;
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  selectedAlbumIds: string[];
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
  locationRadiusFilter: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  sortDirection: SortDirection;
  requestedPage: number;
  pageSize: number;
  dateRangeError: string | null;
  locationError: string | null;
  includeFaceInfo: boolean;
}

export function useLibraryResults({
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
  locationError,
  includeFaceInfo,
}: UseLibraryResultsArgs) {
  const [photos, setPhotos] = useState<LibraryPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [facetHasFacesCounts, setFacetHasFacesCounts] = useState<{ true: number; false: number }>({
    true: 0,
    false: 0,
  });
  const [facetPathHintCounts, setFacetPathHintCounts] = useState<FacetCountEntry[]>([]);
  const [hasConflictingJob, setHasConflictingJob] = useState(false);
  const requestOffset = Math.max(0, (requestedPage - 1) * pageSize);
  const {
    isLoading,
    error,
    reloadToken,
    beginRequest,
    completeRequest,
    failRequest,
    requestRetry,
  } = useRouteRequestState();

  useEffect(() => {
    if (dateRangeError || locationError) {
      setPhotos([]);
      setTotalCount(0);
      return;
    }

    const controller = new AbortController();
    beginRequest();

    fetchLibraryPage(
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
      requestOffset,
      pageSize,
      includeFaceInfo
    )
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }

        setPhotos(payload.hits.items);
        setTotalCount(payload.hits.total);
        setFacetHasFacesCounts(parseHasFacesFacetCounts(payload.facets));
        setFacetPathHintCounts(toPathHintFacetCounts(payload.facets, pathHintFilters));
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
    dateRangeError,
    failRequest,
    fromDate,
    beginRequest,
    completeRequest,
    hasFacesFilter,
    locationError,
    locationRadiusFilter,
    pathHintFilters,
    reloadToken,
    requestOffset,
    selectedAlbumIds,
    selectedPersonNames,
    pageSize,
    personCertaintyMode,
    sortDirection,
    suggestionConfidenceMinDraft,
    toDate,
    includeFaceInfo,
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

  function resetResults() {
    setPhotos([]);
    setTotalCount(0);
  }

  function setFallbackPathHintCounts(pathHints: string[]) {
    setFacetPathHintCounts(
      pathHints.map((value) => ({
        value,
        count: 0,
      }))
    );
  }

  return {
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
    setFallbackPathHintCounts,
  };
}

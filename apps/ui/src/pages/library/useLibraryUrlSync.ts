import { useEffect, useRef } from "react";
import type { Location, NavigateFunction } from "react-router-dom";
import type { LibraryViewRouteState } from "../libraryRouteState";
import { buildLibraryUrlQuery } from "./libraryRouteSearchState";
import { saveLastLibraryUrl, saveLibraryViewState } from "./libraryRouteMemory";
import type {
  LibraryLocationRadius,
  PersonCertaintyMode,
  SearchUrlState,
  SortDirection,
} from "./libraryRouteTypes";

interface UseLibraryUrlSyncArgs {
  location: Location;
  navigate: NavigateFunction;
  parsedUrlState: SearchUrlState;
  parsedUrlStateSignature: string;
  shouldRestoreInitialViewState: boolean;
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
  libraryViewRouteState: LibraryViewRouteState;
  applyParsedUrlState: (parsed: SearchUrlState, shouldApplyViewState: boolean) => void;
}

export function useLibraryUrlSync({
  location,
  navigate,
  parsedUrlState,
  parsedUrlStateSignature,
  shouldRestoreInitialViewState,
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
  applyParsedUrlState,
}: UseLibraryUrlSyncArgs) {
  const suppressNextUrlStateSyncRef = useRef(false);
  const applyingParsedUrlStateRef = useRef(false);
  const lastAppliedParsedUrlStateSignatureRef = useRef<string | null>(parsedUrlStateSignature);
  const shouldRestoreInitialViewStateRef = useRef(shouldRestoreInitialViewState);

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

  useEffect(() => {
    if (suppressNextUrlStateSyncRef.current) {
      suppressNextUrlStateSyncRef.current = false;
      lastAppliedParsedUrlStateSignatureRef.current = parsedUrlStateSignature;
      return;
    }
    if (lastAppliedParsedUrlStateSignatureRef.current === parsedUrlStateSignature) {
      return;
    }

    applyingParsedUrlStateRef.current = true;
    lastAppliedParsedUrlStateSignatureRef.current = parsedUrlStateSignature;

    if (shouldRestoreInitialViewStateRef.current) {
      shouldRestoreInitialViewStateRef.current = false;
      applyParsedUrlState(parsedUrlState, false);
    } else {
      applyParsedUrlState(parsedUrlState, true);
    }
  }, [applyParsedUrlState, parsedUrlState, parsedUrlStateSignature]);

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
      selectedAlbumIds,
      personCertaintyMode,
      suggestionConfidenceMinDraft,
      locationRadius: locationRadiusFilter,
      hasFacesFilter,
      pathHintFilters,
      sortDirection,
      page: requestedPage,
      pageSize,
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
        search: nextQuery ? `?${nextQuery}` : "",
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
    pageSize,
    personCertaintyMode,
    requestedPage,
    selectedAlbumIds,
    selectedPersonNames,
    sortDirection,
    suggestionConfidenceMinDraft,
    toDate,
  ]);

  useEffect(() => {
    saveLastLibraryUrl(`${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  useEffect(() => {
    saveLibraryViewState(location.search, libraryViewRouteState);
  }, [libraryViewRouteState, location.search]);

  return { setPage };
}

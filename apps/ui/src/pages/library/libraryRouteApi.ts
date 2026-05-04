import { isLibraryActionConflictActive } from "./operationsActivity";
import { buildSearchFilters } from "./libraryRouteSearchState";
import {
  DEFAULT_SEARCH_PAGE_LIMIT,
  SEARCH_PAGE_LIMIT_OPTIONS,
  type SearchPageLimit
} from "./libraryPageSize";
import type {
  LibraryLocationRadius,
  PersonCertaintyMode,
  PersonRecord,
  SearchResponsePayload,
  SortDirection
} from "./libraryRouteTypes";

export { DEFAULT_SEARCH_PAGE_LIMIT, SEARCH_PAGE_LIMIT_OPTIONS, type SearchPageLimit };

export async function fetchLibraryPage(
  query: string,
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  personCertaintyMode: PersonCertaintyMode,
  suggestionConfidenceMinDraft: string,
  locationRadius: LibraryLocationRadius | null,
  hasFaces: boolean | null,
  pathHints: string[],
  sortDirection: SortDirection,
  cursor: string | null,
  pageLimit: number
): Promise<SearchResponsePayload> {
  const searchFilters = buildSearchFilters(
    fromDate,
    toDate,
    selectedPersonNames,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
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
        limit: pageLimit,
        cursor
      }
    })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

export async function fetchOperationsActivityConflictState(): Promise<boolean> {
  const response = await fetch("/api/v1/operations/activity");
  if (!response.ok) {
    return false;
  }

  const payload = (await response.json()) as unknown;
  return isLibraryActionConflictActive(payload);
}

export async function fetchPeopleDirectory(): Promise<PersonRecord[]> {
  const response = await fetch("/api/v1/people");
  if (!response.ok) {
    throw new Error("People lookup failed.");
  }
  return (await response.json()) as PersonRecord[];
}

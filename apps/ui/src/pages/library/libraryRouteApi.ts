import { isLibraryActionConflictActive } from "./operationsActivity";
import { buildSearchFilters } from "./libraryRouteSearchState";
import type {
  LibraryLocationRadius,
  PersonRecord,
  SearchResponsePayload,
  SortDirection
} from "./libraryRouteTypes";

export const SEARCH_PAGE_LIMIT = 24;

export async function fetchLibraryPage(
  query: string,
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: LibraryLocationRadius | null,
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
        limit: SEARCH_PAGE_LIMIT,
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

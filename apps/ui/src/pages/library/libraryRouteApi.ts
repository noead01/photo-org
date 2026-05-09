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
import { readErrorDetail } from "../face-labeling/faceLabelingErrors";
import { fetchPeople } from "../people/peopleApi";

export { DEFAULT_SEARCH_PAGE_LIMIT, SEARCH_PAGE_LIMIT_OPTIONS, type SearchPageLimit };

const inFlightLibrarySearchRequests = new Map<string, Promise<SearchResponsePayload>>();
let inFlightOperationsActivityRequest: Promise<boolean> | null = null;
let inFlightPeopleDirectoryRequest: Promise<PersonRecord[]> | null = null;
const inFlightAlbumsRequests = new Map<string, Promise<AlbumRecord[]>>();

export interface AlbumRecord {
  album_id: string;
  name: string;
  owner_user_id: string;
  kind: "editable" | "saved_filter";
  created_ts: string;
  updated_ts: string;
  item_count: number;
  saved_filter?: Record<string, unknown> | null;
}

export interface AlbumDetailItem {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
  thumbnail?: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
}

export interface AlbumDetail extends AlbumRecord {
  items_total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: AlbumDetailItem[];
}

export interface AddAlbumItemsResult {
  album_id: string;
  added_photo_ids: string[];
  duplicate_photo_ids: string[];
  missing_photo_ids: string[];
}

export interface CreateAlbumInput {
  name: string;
  kind?: "editable" | "saved_filter";
  filter_json?: Record<string, unknown> | null;
}

export interface ExportPhotosResult {
  blob: Blob;
  filename: string;
  exportedCount: number;
  skippedCount: number;
}

export async function fetchLibraryPage(
  query: string,
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  selectedAlbumIds: string[],
  personCertaintyMode: PersonCertaintyMode,
  suggestionConfidenceMinDraft: string,
  locationRadius: LibraryLocationRadius | null,
  hasFaces: boolean | null,
  pathHints: string[],
  sortDirection: SortDirection,
  offset: number,
  pageLimit: number
): Promise<SearchResponsePayload> {
  const searchFilters = buildSearchFilters(
    fromDate,
    toDate,
    selectedPersonNames,
    selectedAlbumIds,
    personCertaintyMode,
    suggestionConfidenceMinDraft,
    locationRadius,
    hasFaces,
    pathHints
  );
  const requestBody = {
    ...(query ? { q: query } : {}),
    ...(searchFilters ? { filters: searchFilters } : {}),
    sort: {
      by: "shot_ts",
      dir: sortDirection
    },
    page: {
      limit: pageLimit,
      offset
    }
  };
  const requestKey = JSON.stringify(requestBody);
  const existingRequest = inFlightLibrarySearchRequests.get(requestKey);
  if (existingRequest) {
    return existingRequest;
  }

  const requestPromise = (async () => {
    const response = await fetch("/api/v1/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(requestBody)
    });

    if (!response.ok) {
      throw new Error(`Search request failed (${response.status})`);
    }

    return (await response.json()) as SearchResponsePayload;
  })();

  inFlightLibrarySearchRequests.set(requestKey, requestPromise);
  try {
    return await requestPromise;
  } finally {
    inFlightLibrarySearchRequests.delete(requestKey);
  }
}

export async function fetchOperationsActivityConflictState(): Promise<boolean> {
  if (inFlightOperationsActivityRequest) {
    return inFlightOperationsActivityRequest;
  }

  const requestPromise = (async () => {
    const response = await fetch("/api/v1/operations/activity");
    if (!response.ok) {
      return false;
    }

    const payload = (await response.json()) as unknown;
    return isLibraryActionConflictActive(payload);
  })();

  inFlightOperationsActivityRequest = requestPromise;
  try {
    return await requestPromise;
  } finally {
    inFlightOperationsActivityRequest = null;
  }
}

export async function fetchPeopleDirectory(): Promise<PersonRecord[]> {
  if (inFlightPeopleDirectoryRequest) {
    return inFlightPeopleDirectoryRequest;
  }

  const requestPromise = (async () => {
    try {
      return await fetchPeople();
    } catch {
      throw new Error("People lookup failed.");
    }
  })();

  inFlightPeopleDirectoryRequest = requestPromise;
  try {
    return await requestPromise;
  } finally {
    inFlightPeopleDirectoryRequest = null;
  }
}

export async function fetchAlbums(userId: string | null): Promise<AlbumRecord[]> {
  const requestKey = userId ?? "";
  const existingRequest = inFlightAlbumsRequests.get(requestKey);
  if (existingRequest) {
    return existingRequest;
  }

  const requestPromise = (async () => {
    const response = await fetch("/api/v1/albums", {
      headers: userId ? { "X-Photo-Org-User-Id": userId } : undefined
    });
    if (!response.ok) {
      throw new Error(`Album lookup failed (${response.status}).`);
    }
    return (await response.json()) as AlbumRecord[];
  })();

  inFlightAlbumsRequests.set(requestKey, requestPromise);
  try {
    return await requestPromise;
  } finally {
    inFlightAlbumsRequests.delete(requestKey);
  }
}

export async function createAlbum(
  input: CreateAlbumInput,
  userId: string | null
): Promise<AlbumRecord> {
  const bodyPayload: Record<string, unknown> = {
    name: input.name,
    kind: input.kind ?? "editable"
  };
  if (input.kind === "saved_filter" && input.filter_json) {
    bodyPayload.filter_json = input.filter_json;
  }

  const response = await fetch("/api/v1/albums", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-Photo-Org-User-Id": userId } : {})
    },
    body: JSON.stringify(bodyPayload)
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Album create failed (${response.status}).`);
  }
  return (await response.json()) as AlbumRecord;
}

export async function addPhotosToAlbum(
  albumId: string,
  photoIds: string[],
  userId: string | null
): Promise<AddAlbumItemsResult> {
  const response = await fetch(`/api/v1/albums/${encodeURIComponent(albumId)}/items`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-Photo-Org-User-Id": userId } : {})
    },
    body: JSON.stringify({ photo_ids: photoIds })
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Add to album failed (${response.status}).`);
  }
  return (await response.json()) as AddAlbumItemsResult;
}

export async function fetchAlbumDetail(
  albumId: string,
  options?: { page?: number; pageSize?: number }
): Promise<AlbumDetail> {
  const params = new URLSearchParams();
  if (options?.page && Number.isInteger(options.page) && options.page > 0) {
    params.set("page", String(options.page));
  }
  if (options?.pageSize && Number.isInteger(options.pageSize) && options.pageSize > 0) {
    params.set("page_size", String(options.pageSize));
  }
  const query = params.toString();
  const response = await fetch(
    `/api/v1/albums/${encodeURIComponent(albumId)}${query ? `?${query}` : ""}`
  );
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Album detail lookup failed (${response.status}).`);
  }
  return (await response.json()) as AlbumDetail;
}

export async function updateAlbum(
  albumId: string,
  patch: { name?: string; filter_json?: Record<string, unknown> | null },
  userId: string | null
): Promise<AlbumRecord> {
  const response = await fetch(`/api/v1/albums/${encodeURIComponent(albumId)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...(userId ? { "X-Photo-Org-User-Id": userId } : {})
    },
    body: JSON.stringify(patch)
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Album update failed (${response.status}).`);
  }
  return (await response.json()) as AlbumRecord;
}

export async function deleteAlbum(albumId: string): Promise<void> {
  const response = await fetch(`/api/v1/albums/${encodeURIComponent(albumId)}`, {
    method: "DELETE"
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Album delete failed (${response.status}).`);
  }
}

export async function removePhotoFromAlbum(albumId: string, photoId: string): Promise<void> {
  const response = await fetch(
    `/api/v1/albums/${encodeURIComponent(albumId)}/items/${encodeURIComponent(photoId)}`,
    {
      method: "DELETE"
    }
  );
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new Error(detail ?? `Remove from album failed (${response.status}).`);
  }
}

function parseAttachmentFilename(contentDisposition: string | null): string {
  if (!contentDisposition) {
    return "photo-org-export.zip";
  }

  const match = contentDisposition.match(/filename=\"([^\"]+)\"/i);
  if (!match || !match[1]) {
    return "photo-org-export.zip";
  }
  return match[1];
}

export async function exportPhotos(photoIds: string[]): Promise<ExportPhotosResult> {
  const response = await fetch("/api/v1/exports/photos", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ photo_ids: photoIds })
  });
  if (!response.ok) {
    throw new Error(`Export request failed (${response.status}).`);
  }

  const blob = await response.blob();
  const filename = parseAttachmentFilename(response.headers.get("Content-Disposition"));
  const exportedCount = Number.parseInt(
    response.headers.get("X-Photo-Org-Exported-Count") ?? "0",
    10
  );
  const skippedCount = Number.parseInt(
    response.headers.get("X-Photo-Org-Skipped-Count") ?? "0",
    10
  );
  return {
    blob,
    filename,
    exportedCount: Number.isFinite(exportedCount) ? exportedCount : 0,
    skippedCount: Number.isFinite(skippedCount) ? skippedCount : 0
  };
}

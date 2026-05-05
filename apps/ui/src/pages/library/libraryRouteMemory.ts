import type { SortDirection } from "./libraryRouteTypes";

const LAST_LIBRARY_URL_KEY = "photo-org:library:last-url";
const LIBRARY_VIEW_STATE_KEY_PREFIX = "photo-org:library:view-state:";

export interface StoredLibraryViewState {
  sortDirection: SortDirection;
  cursorByPage: Record<number, string | null>;
}

function resolveSessionStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function saveLastLibraryUrl(target: string): void {
  if (!target.startsWith("/library")) {
    return;
  }
  const storage = resolveSessionStorage();
  if (!storage) {
    return;
  }
  storage.setItem(LAST_LIBRARY_URL_KEY, target);
}

export function loadLastLibraryUrl(): string {
  const storage = resolveSessionStorage();
  if (!storage) {
    return "/library";
  }
  const value = storage.getItem(LAST_LIBRARY_URL_KEY);
  if (!value || !value.startsWith("/library")) {
    return "/library";
  }
  return value;
}

export function buildLibraryViewStateStorageKey(search: string): string {
  const params = new URLSearchParams(search);
  params.delete("page");
  return `${LIBRARY_VIEW_STATE_KEY_PREFIX}${params.toString()}`;
}

export function saveLibraryViewState(search: string, viewState: StoredLibraryViewState): void {
  const storage = resolveSessionStorage();
  if (!storage) {
    return;
  }
  storage.setItem(buildLibraryViewStateStorageKey(search), JSON.stringify(viewState));
}

export function loadLibraryViewState(search: string): StoredLibraryViewState | null {
  const storage = resolveSessionStorage();
  if (!storage) {
    return null;
  }

  const rawValue = storage.getItem(buildLibraryViewStateStorageKey(search));
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as {
      sortDirection?: unknown;
      cursorByPage?: unknown;
    };
    if (parsed.sortDirection !== "asc" && parsed.sortDirection !== "desc") {
      return null;
    }
    if (
      typeof parsed.cursorByPage !== "object"
      || parsed.cursorByPage === null
      || Array.isArray(parsed.cursorByPage)
    ) {
      return null;
    }

    const cursorByPage: Record<number, string | null> = {};
    for (const [key, cursor] of Object.entries(parsed.cursorByPage)) {
      const pageNumber = Number.parseInt(key, 10);
      if (!Number.isInteger(pageNumber) || pageNumber < 1) {
        continue;
      }
      if (typeof cursor !== "string" && cursor !== null) {
        continue;
      }
      cursorByPage[pageNumber] = cursor;
    }
    if (cursorByPage[1] === undefined) {
      cursorByPage[1] = null;
    }

    return {
      sortDirection: parsed.sortDirection,
      cursorByPage
    };
  } catch {
    return null;
  }
}

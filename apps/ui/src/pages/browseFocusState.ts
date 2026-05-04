import {
  parseLibrarySelectionRouteState,
  type LibrarySelectionRouteState
} from "./library/librarySelection";
import type { SortDirection } from "./library/libraryRouteTypes";

export interface LibraryViewRouteState {
  sortDirection: SortDirection;
  cursorByPage: Record<number, string | null>;
}

export interface BrowseReturnState {
  restoreFocusPhotoId?: string;
  librarySelection?: LibrarySelectionRouteState;
  libraryViewState?: LibraryViewRouteState;
}

export interface DetailReturnState {
  returnToLibrarySearch?: string;
  returnFocusPhotoId?: string;
  librarySelection?: LibrarySelectionRouteState;
  libraryViewState?: LibraryViewRouteState;
}

let pendingBrowseFocusPhotoId: string | null = null;

export function setPendingBrowseFocusPhotoId(photoId: string): void {
  pendingBrowseFocusPhotoId = photoId;
}

export function consumePendingBrowseFocusPhotoId(): string | null {
  const photoId = pendingBrowseFocusPhotoId;
  pendingBrowseFocusPhotoId = null;
  return photoId;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function resolveBrowseReturnState(state: unknown): BrowseReturnState | null {
  if (!isRecord(state)) {
    return null;
  }

  const restoreFocusPhotoId = state.restoreFocusPhotoId;
  const librarySelection = parseLibrarySelectionRouteState(
    state.librarySelection ?? state.browseSelection
  );
  const libraryViewState = parseLibraryViewRouteState(state.libraryViewState);
  const hasRestoreFocusPhotoId =
    typeof restoreFocusPhotoId === "string" && restoreFocusPhotoId.length > 0;

  if (!hasRestoreFocusPhotoId && !librarySelection && !libraryViewState) {
    return null;
  }

  return {
    restoreFocusPhotoId: hasRestoreFocusPhotoId ? restoreFocusPhotoId : undefined,
    librarySelection: librarySelection ?? undefined,
    libraryViewState: libraryViewState ?? undefined
  };
}

export function resolveDetailReturnState(state: unknown): DetailReturnState {
  if (!isRecord(state)) {
    return {};
  }

  const returnState: DetailReturnState = {};
  if (typeof state.returnToLibrarySearch === "string") {
    returnState.returnToLibrarySearch = state.returnToLibrarySearch;
  } else if (typeof state.returnToBrowseSearch === "string") {
    returnState.returnToLibrarySearch = state.returnToBrowseSearch;
  }
  if (typeof state.returnFocusPhotoId === "string" && state.returnFocusPhotoId.length > 0) {
    returnState.returnFocusPhotoId = state.returnFocusPhotoId;
  }
  const librarySelection = parseLibrarySelectionRouteState(
    state.librarySelection ?? state.browseSelection
  );
  if (librarySelection) {
    returnState.librarySelection = librarySelection;
  }
  const libraryViewState = parseLibraryViewRouteState(state.libraryViewState);
  if (libraryViewState) {
    returnState.libraryViewState = libraryViewState;
  }

  return returnState;
}

function parseLibraryViewRouteState(value: unknown): LibraryViewRouteState | null {
  if (!isRecord(value)) {
    return null;
  }

  const sortDirection = value.sortDirection;
  if (sortDirection !== "asc" && sortDirection !== "desc") {
    return null;
  }

  const cursorByPageValue = value.cursorByPage;
  if (!isRecord(cursorByPageValue)) {
    return null;
  }

  const cursorByPage: Record<number, string | null> = {};
  for (const [key, cursor] of Object.entries(cursorByPageValue)) {
    const pageNumber = Number.parseInt(key, 10);
    if (!Number.isInteger(pageNumber) || pageNumber < 1) {
      return null;
    }
    if (typeof cursor !== "string" && cursor !== null) {
      return null;
    }
    cursorByPage[pageNumber] = cursor;
  }

  if (cursorByPage[1] === undefined) {
    cursorByPage[1] = null;
  }

  return {
    sortDirection,
    cursorByPage
  };
}

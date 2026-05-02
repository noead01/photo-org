import {
  parseLibrarySelectionRouteState,
  type LibrarySelectionRouteState
} from "./library/librarySelection";

export interface BrowseReturnState {
  restoreFocusPhotoId?: string;
  librarySelection?: LibrarySelectionRouteState;
}

export interface DetailReturnState {
  returnToLibrarySearch?: string;
  returnFocusPhotoId?: string;
  librarySelection?: LibrarySelectionRouteState;
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
  const hasRestoreFocusPhotoId =
    typeof restoreFocusPhotoId === "string" && restoreFocusPhotoId.length > 0;

  if (!hasRestoreFocusPhotoId && !librarySelection) {
    return null;
  }

  return {
    restoreFocusPhotoId: hasRestoreFocusPhotoId ? restoreFocusPhotoId : undefined,
    librarySelection: librarySelection ?? undefined
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

  return returnState;
}

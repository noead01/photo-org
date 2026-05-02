import {
  parseLibrarySelectionRouteState,
  type LibrarySelectionRouteState
} from "./library/librarySelection";

export interface BrowseReturnState {
  restoreFocusPhotoId?: string;
  browseSelection?: LibrarySelectionRouteState;
}

export interface DetailReturnState {
  returnToBrowseSearch?: string;
  returnFocusPhotoId?: string;
  browseSelection?: LibrarySelectionRouteState;
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
  const browseSelection = parseLibrarySelectionRouteState(state.browseSelection);
  const hasRestoreFocusPhotoId =
    typeof restoreFocusPhotoId === "string" && restoreFocusPhotoId.length > 0;

  if (!hasRestoreFocusPhotoId && !browseSelection) {
    return null;
  }

  return {
    restoreFocusPhotoId: hasRestoreFocusPhotoId ? restoreFocusPhotoId : undefined,
    browseSelection: browseSelection ?? undefined
  };
}

export function resolveDetailReturnState(state: unknown): DetailReturnState {
  if (!isRecord(state)) {
    return {};
  }

  const returnState: DetailReturnState = {};
  if (typeof state.returnToBrowseSearch === "string") {
    returnState.returnToBrowseSearch = state.returnToBrowseSearch;
  }
  if (typeof state.returnFocusPhotoId === "string" && state.returnFocusPhotoId.length > 0) {
    returnState.returnFocusPhotoId = state.returnFocusPhotoId;
  }
  const browseSelection = parseLibrarySelectionRouteState(state.browseSelection);
  if (browseSelection) {
    returnState.browseSelection = browseSelection;
  }

  return returnState;
}

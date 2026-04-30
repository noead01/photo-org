export interface BrowseReturnState {
  restoreFocusPhotoId?: string;
}

export interface DetailReturnState {
  returnToBrowseSearch?: string;
  returnFocusPhotoId?: string;
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
  if (typeof restoreFocusPhotoId !== "string" || restoreFocusPhotoId.length === 0) {
    return null;
  }

  return { restoreFocusPhotoId };
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

  return returnState;
}

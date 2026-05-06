import {
  parseLibrarySelectionRouteState,
  type LibrarySelectionRouteState
} from "./library/librarySelection";
import type { SortDirection } from "./library/libraryRouteTypes";

export interface LibraryViewRouteState {
  sortDirection: SortDirection;
  page: number;
  pageSize: number;
}

export interface LibraryReturnState {
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

let pendingLibraryFocusPhotoId: string | null = null;

export function setPendingLibraryFocusPhotoId(photoId: string): void {
  pendingLibraryFocusPhotoId = photoId;
}

export function consumePendingLibraryFocusPhotoId(): string | null {
  const photoId = pendingLibraryFocusPhotoId;
  pendingLibraryFocusPhotoId = null;
  return photoId;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function resolveLibraryReturnState(state: unknown): LibraryReturnState | null {
  if (!isRecord(state)) {
    return null;
  }

  const restoreFocusPhotoId = state.restoreFocusPhotoId;
  const librarySelection = parseLibrarySelectionRouteState(state.librarySelection);
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
  }
  if (typeof state.returnFocusPhotoId === "string" && state.returnFocusPhotoId.length > 0) {
    returnState.returnFocusPhotoId = state.returnFocusPhotoId;
  }
  const librarySelection = parseLibrarySelectionRouteState(state.librarySelection);
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

  const pageValue = value.page;
  if (typeof pageValue !== "number" || !Number.isInteger(pageValue) || pageValue < 1) {
    return null;
  }

  const pageSizeValue = value.pageSize;
  if (typeof pageSizeValue !== "number" || !Number.isInteger(pageSizeValue) || pageSizeValue < 1) {
    return null;
  }

  return {
    sortDirection,
    page: pageValue,
    pageSize: pageSizeValue,
  };
}

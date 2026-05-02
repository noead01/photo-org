export type LibrarySelectionScope = "selected" | "page" | "allFiltered";

export interface LibrarySelectionState {
  scope: LibrarySelectionScope;
  selectedPhotoIds: Set<string>;
  allFilteredFingerprint: string | null;
}

export interface LibrarySelectionRouteState {
  scope: LibrarySelectionScope;
  selectedPhotoIds: string[];
  allFilteredFingerprint: string | null;
}

type TogglePhotoSelectionAction = {
  type: "togglePhotoSelection";
  photoId: string;
};

type SetScopeAction = {
  type: "setScope";
  scope: LibrarySelectionScope;
  activeFilterFingerprint: string;
};

type FiltersChangedAction = {
  type: "filtersChanged";
  activeFilterFingerprint: string;
};

type ClearExplicitSelectionAction = {
  type: "clearExplicitSelection";
};

export type LibrarySelectionAction =
  | TogglePhotoSelectionAction
  | SetScopeAction
  | FiltersChangedAction
  | ClearExplicitSelectionAction;

export const DEFAULT_LIBRARY_SELECTION_STATE: LibrarySelectionState = {
  scope: "selected",
  selectedPhotoIds: new Set<string>(),
  allFilteredFingerprint: null
};

export function parseLibrarySelectionRouteState(
  value: unknown
): LibrarySelectionRouteState | null {
  if (!isRecord(value)) {
    return null;
  }

  const scope = value.scope;
  const selectedPhotoIds = value.selectedPhotoIds;
  const allFilteredFingerprint = value.allFilteredFingerprint;

  if (
    scope !== "selected" &&
    scope !== "page" &&
    scope !== "allFiltered"
  ) {
    return null;
  }

  if (!Array.isArray(selectedPhotoIds) || !selectedPhotoIds.every((id) => typeof id === "string")) {
    return null;
  }

  if (
    allFilteredFingerprint !== null &&
    typeof allFilteredFingerprint !== "string"
  ) {
    return null;
  }

  return {
    scope,
    selectedPhotoIds: dedupeNonEmptyStrings(selectedPhotoIds),
    allFilteredFingerprint
  };
}

export function createLibrarySelectionState(
  routeState: LibrarySelectionRouteState | null
): LibrarySelectionState {
  if (!routeState) {
    return cloneLibrarySelectionState(DEFAULT_LIBRARY_SELECTION_STATE);
  }

  return {
    scope: routeState.scope,
    selectedPhotoIds: new Set<string>(routeState.selectedPhotoIds),
    allFilteredFingerprint:
      routeState.scope === "allFiltered" ? routeState.allFilteredFingerprint : null
  };
}

export function serializeLibrarySelectionState(
  state: LibrarySelectionState
): LibrarySelectionRouteState {
  return {
    scope: state.scope,
    selectedPhotoIds: Array.from(state.selectedPhotoIds).sort((left, right) =>
      left.localeCompare(right, "en-US")
    ),
    allFilteredFingerprint:
      state.scope === "allFiltered" ? state.allFilteredFingerprint : null
  };
}

export function librarySelectionReducer(
  state: LibrarySelectionState,
  action: LibrarySelectionAction
): LibrarySelectionState {
  if (action.type === "togglePhotoSelection") {
    const normalizedPhotoId = action.photoId.trim();
    if (normalizedPhotoId.length === 0) {
      return state;
    }

    const nextSelectedPhotoIds = new Set(state.selectedPhotoIds);
    if (nextSelectedPhotoIds.has(normalizedPhotoId)) {
      nextSelectedPhotoIds.delete(normalizedPhotoId);
    } else {
      nextSelectedPhotoIds.add(normalizedPhotoId);
    }

    return {
      ...state,
      selectedPhotoIds: nextSelectedPhotoIds
    };
  }

  if (action.type === "setScope") {
    return {
      ...state,
      scope: action.scope,
      allFilteredFingerprint:
        action.scope === "allFiltered" ? action.activeFilterFingerprint : null
    };
  }

  if (action.type === "filtersChanged") {
    if (
      state.scope === "allFiltered" &&
      state.allFilteredFingerprint !== action.activeFilterFingerprint
    ) {
      return {
        ...state,
        scope: "selected",
        allFilteredFingerprint: null
      };
    }

    return state;
  }

  if (action.type === "clearExplicitSelection") {
    if (state.selectedPhotoIds.size === 0) {
      return state;
    }
    return {
      ...state,
      selectedPhotoIds: new Set<string>()
    };
  }

  return state;
}

interface LibrarySelectionCountInput {
  currentPageCount: number;
  totalFilteredCount: number;
}

export function resolveSelectionScopeCount(
  state: LibrarySelectionState,
  input: LibrarySelectionCountInput
): number {
  if (state.scope === "page") {
    return input.currentPageCount;
  }

  if (state.scope === "allFiltered") {
    return input.totalFilteredCount;
  }

  return state.selectedPhotoIds.size;
}

export function formatSelectionScopeLabel(scope: LibrarySelectionScope): string {
  if (scope === "allFiltered") {
    return "All filtered";
  }
  if (scope === "page") {
    return "This page";
  }
  return "Selected";
}

function cloneLibrarySelectionState(state: LibrarySelectionState): LibrarySelectionState {
  return {
    scope: state.scope,
    selectedPhotoIds: new Set<string>(state.selectedPhotoIds),
    allFilteredFingerprint: state.allFilteredFingerprint
  };
}

function dedupeNonEmptyStrings(values: string[]): string[] {
  const unique = new Set<string>();
  for (const value of values) {
    const trimmed = value.trim();
    if (trimmed.length > 0) {
      unique.add(trimmed);
    }
  }
  return Array.from(unique);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

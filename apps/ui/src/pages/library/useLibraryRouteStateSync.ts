import { useEffect, useMemo } from "react";
import type { Location, NavigateFunction } from "react-router-dom";
import {
  parseLibrarySelectionRouteState,
  serializeLibrarySelectionState,
  type LibrarySelectionState,
} from "./librarySelection";
import { resolveLibraryReturnState, type LibraryViewRouteState } from "../libraryRouteState";

interface UseLibraryRouteStateSyncArgs {
  location: Location;
  navigate: NavigateFunction;
  selectionState: LibrarySelectionState;
  libraryViewRouteState: LibraryViewRouteState;
}

export function useLibraryRouteStateSync({
  location,
  navigate,
  selectionState,
  libraryViewRouteState,
}: UseLibraryRouteStateSyncArgs) {
  const selectionRouteState = useMemo(
    () => serializeLibrarySelectionState(selectionState),
    [selectionState]
  );

  useEffect(() => {
    const currentRouteState = resolveLibraryReturnState(location.state);
    const currentRouteSelection = currentRouteState?.librarySelection ?? null;
    const currentRouteViewState = currentRouteState?.libraryViewState ?? null;

    if (
      areSelectionRouteStatesEqual(currentRouteSelection, selectionRouteState)
      && areLibraryViewRouteStatesEqual(currentRouteViewState, libraryViewRouteState)
    ) {
      return;
    }

    const routeState = isRecord(location.state) ? location.state : {};
    navigate(
      {
        pathname: location.pathname,
        search: location.search,
      },
      {
        replace: true,
        state: {
          ...routeState,
          librarySelection: selectionRouteState,
          libraryViewState: libraryViewRouteState,
        },
      }
    );
  }, [libraryViewRouteState, location.pathname, location.search, location.state, navigate, selectionRouteState]);

  return { selectionRouteState };
}

function areSelectionRouteStatesEqual(
  left: ReturnType<typeof parseLibrarySelectionRouteState>,
  right: ReturnType<typeof serializeLibrarySelectionState>
): boolean {
  if (!left) {
    return false;
  }
  if (left.scope !== right.scope) {
    return false;
  }
  if (left.allFilteredFingerprint !== right.allFilteredFingerprint) {
    return false;
  }
  if (left.selectedPhotoIds.length !== right.selectedPhotoIds.length) {
    return false;
  }

  return left.selectedPhotoIds.every((photoId, index) => photoId === right.selectedPhotoIds[index]);
}

function areLibraryViewRouteStatesEqual(
  left: LibraryViewRouteState | null,
  right: LibraryViewRouteState
): boolean {
  if (!left) {
    return false;
  }
  if (left.sortDirection !== right.sortDirection) {
    return false;
  }
  if (left.pageSize !== right.pageSize) {
    return false;
  }
  return left.page === right.page;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

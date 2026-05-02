export interface LibraryActionAvailability {
  enabled: boolean;
  reason: string | null;
}

export interface LibraryActionBarState {
  addToAlbum: LibraryActionAvailability;
  export: LibraryActionAvailability;
}

interface ResolveLibraryActionStateInput {
  selectionCount: number;
  canAddToAlbum: boolean;
  canExport: boolean;
  hasConflictingJob: boolean;
}

function resolveReason(
  enabled: boolean,
  selectionCount: number,
  hasPermission: boolean,
  hasConflictingJob: boolean
): string | null {
  if (enabled) {
    return null;
  }

  if (selectionCount <= 0) {
    return "No selection scope active.";
  }

  if (!hasPermission) {
    return "You do not have permission for this action.";
  }

  if (hasConflictingJob) {
    return "Action temporarily unavailable while ingest processing is active.";
  }

  return "Action unavailable.";
}

export function resolveLibraryActionState(
  input: ResolveLibraryActionStateInput
): LibraryActionBarState {
  const addEnabled =
    input.selectionCount > 0 &&
    input.canAddToAlbum &&
    !input.hasConflictingJob;
  const exportEnabled =
    input.selectionCount > 0 &&
    input.canExport &&
    !input.hasConflictingJob;

  return {
    addToAlbum: {
      enabled: addEnabled,
      reason: resolveReason(
        addEnabled,
        input.selectionCount,
        input.canAddToAlbum,
        input.hasConflictingJob
      )
    },
    export: {
      enabled: exportEnabled,
      reason: resolveReason(
        exportEnabled,
        input.selectionCount,
        input.canExport,
        input.hasConflictingJob
      )
    }
  };
}

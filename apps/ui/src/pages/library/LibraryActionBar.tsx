import type { LibraryActionBarState } from "./libraryActionBarState";

type LibraryActionKey = "addToAlbum" | "export";

interface LibraryActionBarProps {
  selectionCount: number;
  actionState: LibraryActionBarState;
  onAction: (action: LibraryActionKey) => void;
}

export function LibraryActionBar({
  selectionCount,
  actionState,
  onAction
}: LibraryActionBarProps) {
  if (selectionCount <= 0) {
    return null;
  }

  const addReasonId = actionState.addToAlbum.reason
    ? "library-action-add-reason"
    : undefined;
  const exportReasonId = actionState.export.reason
    ? "library-action-export-reason"
    : undefined;

  return (
    <section className="library-action-bar" aria-label="Library actions">
      <p className="library-action-summary">
        {selectionCount} selected
      </p>
      <div
        className="library-action-buttons"
        role="group"
        aria-label="Library action buttons"
      >
        <button
          type="button"
          disabled={!actionState.addToAlbum.enabled}
          aria-describedby={addReasonId}
          onClick={() => onAction("addToAlbum")}
        >
          Add to album
        </button>
        {actionState.addToAlbum.reason ? (
          <p id={addReasonId} className="library-action-reason">
            {actionState.addToAlbum.reason}
          </p>
        ) : null}
        <button
          type="button"
          disabled={!actionState.export.enabled}
          aria-describedby={exportReasonId}
          onClick={() => onAction("export")}
        >
          Export
        </button>
        {actionState.export.reason ? (
          <p id={exportReasonId} className="library-action-reason">
            {actionState.export.reason}
          </p>
        ) : null}
      </div>
    </section>
  );
}

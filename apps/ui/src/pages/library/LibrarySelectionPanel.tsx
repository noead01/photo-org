import {
  formatSelectionScopeLabel,
  type LibrarySelectionScope,
  type LibrarySelectionState
} from "./librarySelection";

interface LibrarySelectionPanelProps {
  selectionState: LibrarySelectionState;
  activeScopeCount: number;
  areFaceBoxesVisible: boolean;
  areAlbumInteractionsVisible: boolean;
  onSetScope: (scope: LibrarySelectionScope) => void;
  onClearExplicitSelection: () => void;
  onFaceBoxesVisibleChange: (visible: boolean) => void;
  onAlbumInteractionsVisibleChange: (visible: boolean) => void;
}

export function LibrarySelectionPanel({
  selectionState,
  activeScopeCount,
  areFaceBoxesVisible,
  areAlbumInteractionsVisible,
  onSetScope,
  onClearExplicitSelection,
  onFaceBoxesVisibleChange,
  onAlbumInteractionsVisibleChange
}: LibrarySelectionPanelProps) {
  return (
    <section className="browse-selection-panel" aria-label="Library selection controls">
      <fieldset className="browse-selection-scope-group">
        <legend>Selection scope</legend>
        <label>
          <input
            type="radio"
            name="library-selection-scope"
            value="selected"
            checked={selectionState.scope === "selected"}
            onChange={() => onSetScope("selected")}
          />
          Selected
        </label>
        <label>
          <input
            type="radio"
            name="library-selection-scope"
            value="page"
            checked={selectionState.scope === "page"}
            onChange={() => onSetScope("page")}
          />
          This page
        </label>
        <label>
          <input
            type="radio"
            name="library-selection-scope"
            value="allFiltered"
            checked={selectionState.scope === "allFiltered"}
            onChange={() => onSetScope("allFiltered")}
          />
          All filtered
        </label>
      </fieldset>
      <p className="browse-selection-summary" aria-live="polite">
        {`${formatSelectionScopeLabel(selectionState.scope)} scope: ${activeScopeCount} photo${activeScopeCount === 1 ? "" : "s"}`}
      </p>
      <button
        type="button"
        onClick={onClearExplicitSelection}
        disabled={selectionState.selectedPhotoIds.size === 0}
      >
        Clear selected
      </button>
      <label>
        <input
          type="checkbox"
          checked={areFaceBoxesVisible}
          onChange={(event) => {
            onFaceBoxesVisibleChange(event.currentTarget.checked);
          }}
        />
        Show face boxes on all photos
      </label>
      <label>
        <input
          type="checkbox"
          checked={areAlbumInteractionsVisible}
          onChange={(event) => {
            onAlbumInteractionsVisibleChange(event.currentTarget.checked);
          }}
        />
        Enable album assignment widgets
      </label>
    </section>
  );
}

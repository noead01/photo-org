import type { FormEvent } from "react";

interface AddToAlbumDialogProps {
  isOpen: boolean;
  isSaving: boolean;
  photoCount: number;
  albumKind: "editable" | "saved_filter";
  albumName: string;
  showAlbumTypeInfo: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onAlbumKindChange: (kind: "editable" | "saved_filter") => void;
  onAlbumNameChange: (value: string) => void;
  onToggleAlbumTypeInfo: () => void;
}

function formatPhotoCountLabel(count: number): string {
  return `${count} photo${count === 1 ? "" : "s"}`;
}

export function AddToAlbumDialog({
  isOpen,
  isSaving,
  photoCount,
  albumKind,
  albumName,
  showAlbumTypeInfo,
  error,
  onClose,
  onSubmit,
  onAlbumKindChange,
  onAlbumNameChange,
  onToggleAlbumTypeInfo
}: AddToAlbumDialogProps) {
  if (!isOpen) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        className="add-to-album-modal-backdrop"
        aria-label="Close add to album modal"
        onClick={onClose}
      />
      <section
        className="add-to-album-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Add to album"
      >
        <div className="add-to-album-modal-header">
          <h3>Add to album</h3>
          <button type="button" onClick={onClose} disabled={isSaving}>
            Close
          </button>
        </div>
        <form className="add-to-album-modal-form" onSubmit={onSubmit}>
          <p>Selection snapshot: {formatPhotoCountLabel(photoCount)}.</p>
          <fieldset className="add-to-album-modal-type-group">
            <legend>Album type</legend>
            <label>
              <input
                type="radio"
                name="add-to-album-kind"
                value="editable"
                checked={albumKind === "editable"}
                onChange={() => onAlbumKindChange("editable")}
                disabled={isSaving}
              />
              Editable
            </label>
            <label>
              <input
                type="radio"
                name="add-to-album-kind"
                value="saved_filter"
                checked={albumKind === "saved_filter"}
                onChange={() => onAlbumKindChange("saved_filter")}
                disabled={isSaving}
              />
              Saved Filter
            </label>
            <button
              type="button"
              className="add-to-album-modal-info"
              aria-label="Album type info"
              aria-expanded={showAlbumTypeInfo}
              onClick={onToggleAlbumTypeInfo}
              disabled={isSaving}
            >
              i
            </button>
          </fieldset>
          {showAlbumTypeInfo ? (
            <p className="add-to-album-modal-help">
              Editable albums store explicit photo membership. Saved Filter albums follow active
              filters and update automatically.
            </p>
          ) : null}
          <label htmlFor="add-to-album-name">Album name</label>
          <input
            id="add-to-album-name"
            value={albumName}
            onChange={(event) => onAlbumNameChange(event.target.value)}
            disabled={isSaving}
          />
          {albumKind === "saved_filter" ? (
            <p className="add-to-album-modal-help">
              This will create a dynamic album from the current filter state.
            </p>
          ) : (
            <p className="add-to-album-modal-help">
              Selected photos will be added uniquely after creation.
            </p>
          )}
          {error ? <p role="alert">{error}</p> : null}
          <div className="add-to-album-modal-actions">
            <button type="button" onClick={onClose} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" disabled={isSaving}>
              Save to album
            </button>
          </div>
        </form>
      </section>
    </>
  );
}

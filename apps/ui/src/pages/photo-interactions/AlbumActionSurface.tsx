import { useMemo, useState } from "react";
import "./photo-interactions.css";
import type { AlbumTarget } from "./photoInteractionTypes";

interface AlbumActionSurfaceProps {
  albums: AlbumTarget[];
  selectedPhotoIds: string[];
  isSubmitting: boolean;
  resultMessage: string | null;
  onAddToAlbum: (albumId: string, photoIds: string[]) => void;
  onCreateAlbumAndAdd: (name: string, photoIds: string[]) => void;
}

export function AlbumActionSurface({
  albums,
  selectedPhotoIds,
  isSubmitting,
  resultMessage,
  onAddToAlbum,
  onCreateAlbumAndAdd
}: AlbumActionSurfaceProps) {
  const [selectedAlbumId, setSelectedAlbumId] = useState("");
  const [newAlbumName, setNewAlbumName] = useState("");

  const eligibleAlbums = useMemo(
    () => albums.filter((album) => album.canAcceptManualAdditions),
    [albums]
  );
  const countLabel = `${selectedPhotoIds.length} photo${selectedPhotoIds.length === 1 ? "" : "s"}`;
  const disabled = isSubmitting || selectedPhotoIds.length === 0;

  return (
    <section className="album-action-surface" aria-label="Album actions">
      <label>
        Album
        <select
          aria-label="Album target"
          value={selectedAlbumId}
          disabled={disabled}
          onChange={(event) => setSelectedAlbumId(event.currentTarget.value)}
        >
          <option value="">Select album</option>
          {eligibleAlbums.map((album) => (
            <option key={album.albumId} value={album.albumId}>
              {album.name}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        disabled={disabled || selectedAlbumId.length === 0}
        onClick={() => onAddToAlbum(selectedAlbumId, selectedPhotoIds)}
      >
        Add {countLabel}
      </button>

      <label>
        New album
        <input
          aria-label="New album name"
          value={newAlbumName}
          disabled={disabled}
          onChange={(event) => setNewAlbumName(event.currentTarget.value)}
        />
      </label>
      <button
        type="button"
        disabled={disabled || newAlbumName.trim().length === 0}
        onClick={() => onCreateAlbumAndAdd(newAlbumName.trim(), selectedPhotoIds)}
      >
        Create and add {countLabel}
      </button>

      {resultMessage ? <p className="album-action-result">{resultMessage}</p> : null}
    </section>
  );
}

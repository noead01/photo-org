import { Link } from "react-router-dom";
import { FaceOverlayLayer } from "./FaceOverlayLayer";
import type { PhotoSummary } from "./photoInteractionTypes";

interface PhotoSurfaceProps {
  photo: PhotoSummary;
  selected: boolean;
  faceBoxesVisible: boolean;
  activeMetadata: boolean;
  detailTo: string;
  onToggleSelected: (photoId: string) => void;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string) => void;
}

export function buildPhotoSurfaceId(photoId: string): string {
  return `photo-surface-${photoId}`;
}

export function PhotoSurface({
  photo,
  selected,
  faceBoxesVisible,
  activeMetadata,
  detailTo,
  onToggleSelected,
  onOpenMetadata,
  onOpenFace,
}: PhotoSurfaceProps) {
  const surfaceId = buildPhotoSurfaceId(photo.photoId);
  const thumbnail = photo.media.thumbnail;

  return (
    <article
      data-testid={surfaceId}
      className={`photo-surface${selected ? " photo-surface-selected" : ""}${activeMetadata ? " photo-surface-active-metadata" : ""}`}
    >
      <label className="photo-surface-select">
        <input
          type="checkbox"
          checked={selected}
          aria-label={`Select photo ${photo.title}`}
          onChange={() => onToggleSelected(photo.photoId)}
        />
      </label>

      <div
        className="photo-surface-media"
        style={thumbnail ? { aspectRatio: `${thumbnail.width} / ${thumbnail.height}` } : undefined}
      >
        <Link className="photo-surface-link" to={detailTo} aria-label={`Open details for ${photo.title}`}>
          {thumbnail ? (
            <img
              className="photo-surface-image"
              src={`data:${thumbnail.mimeType};base64,${thumbnail.dataBase64}`}
              width={thumbnail.width}
              height={thumbnail.height}
              alt={`Preview of ${photo.path}`}
            />
          ) : (
            <div className="photo-surface-placeholder" aria-hidden="true">
              No preview
            </div>
          )}
        </Link>

        <FaceOverlayLayer
          faces={photo.faces}
          thumbnailSize={thumbnail ? { width: thumbnail.width, height: thumbnail.height } : null}
          visible={faceBoxesVisible}
          onOpenFace={(faceId) => onOpenFace(photo.photoId, faceId, surfaceId)}
        />
      </div>

      <div className="photo-surface-body">
        <p className="photo-surface-title" title={photo.path}>
          {photo.title}
        </p>
        <button
          type="button"
          className="photo-surface-metadata-button"
          onClick={() => onOpenMetadata(photo.photoId, surfaceId)}
          aria-label={`Show metadata for ${photo.title}`}
        >
          Show metadata
        </button>
      </div>
    </article>
  );
}

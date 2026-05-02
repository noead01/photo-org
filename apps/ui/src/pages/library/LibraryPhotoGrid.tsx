import { Link } from "react-router-dom";
import { deriveIngestStatus } from "../../app/ingestStatus";
import { LibraryPhotoFacePanel } from "./LibraryPhotoFacePanel";
import { PhotoResultIdentity } from "./PhotoResultIdentity";
import {
  formatFilesize,
  formatShotTimestamp
} from "./libraryRouteFormatting";
import type { LibraryPhoto } from "./libraryRouteTypes";
import type { serializeLibrarySelectionState } from "./librarySelection";

interface LibraryPhotoGridProps {
  photos: LibraryPhoto[];
  selectedPhotoIds: Set<string>;
  locationSearch: string;
  selectionRouteState: ReturnType<typeof serializeLibrarySelectionState>;
  onToggleSelection: (photoId: string) => void;
}

export function LibraryPhotoGrid({
  photos,
  selectedPhotoIds,
  locationSearch,
  selectionRouteState,
  onToggleSelection
}: LibraryPhotoGridProps) {
  return (
    <ol className="browse-grid" aria-label="Photo gallery">
      {photos.map((photo) => {
        const ingestStatus = deriveIngestStatus({
          availabilityState: photo.original?.availability_state ?? null,
          isAvailable: photo.original?.is_available ?? null,
          lastFailureReason: photo.original?.last_failure_reason ?? null,
          hasThumbnail: Boolean(photo.thumbnail)
        });

        return (
          <li key={photo.photo_id} className="browse-card">
            <p className="browse-ingest-status">
              <span className={`ingest-status-badge is-${ingestStatus.tone}`}>
                {ingestStatus.label}
              </span>
              <span className="browse-ingest-status-detail">{ingestStatus.description}</span>
            </p>
            <label className="browse-card-selection">
              <input
                type="checkbox"
                checked={selectedPhotoIds.has(photo.photo_id)}
                onChange={() => onToggleSelection(photo.photo_id)}
              />
              Select photo
            </label>
            {photo.thumbnail ? (
              <img
                className="browse-thumbnail"
                src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                width={photo.thumbnail.width}
                height={photo.thumbnail.height}
                alt={`Thumbnail for ${photo.photo_id}`}
              />
            ) : (
              <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                No preview
              </div>
            )}
            <div className="browse-card-body">
              <PhotoResultIdentity
                title={
                  <Link
                    className="browse-photo-link"
                    data-photo-id={photo.photo_id}
                    to={`/library/${photo.photo_id}`}
                    state={{
                      returnToLibrarySearch: locationSearch,
                      returnFocusPhotoId: photo.photo_id,
                      librarySelection: selectionRouteState
                    }}
                  >
                    {photo.photo_id}
                  </Link>
                }
                path={photo.path}
                pathClassName="browse-path"
              />
              <dl>
                <div>
                  <dt>Captured</dt>
                  <dd>{formatShotTimestamp(photo.shot_ts)}</dd>
                </div>
                <div>
                  <dt>Size</dt>
                  <dd>{formatFilesize(photo.filesize)}</dd>
                </div>
                <div>
                  <dt>People</dt>
                  <dd>{photo.people?.length ?? 0}</dd>
                </div>
                <div>
                  <dt>Original</dt>
                  <dd>{photo.original?.availability_state ?? "unknown"}</dd>
                </div>
              </dl>
            </div>
            <LibraryPhotoFacePanel photo={photo} />
          </li>
        );
      })}
    </ol>
  );
}

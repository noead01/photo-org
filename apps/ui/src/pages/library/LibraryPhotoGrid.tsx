import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../../app/ingestStatus";
import {
  buildFaceOverlayRegions,
  FaceBBoxOverlay,
  type FaceBBoxOverlayFace
} from "../FaceBBoxOverlay";
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
  showAllFaceBoxes: boolean;
  selectedPhotoIds: Set<string>;
  locationSearch: string;
  selectionRouteState: ReturnType<typeof serializeLibrarySelectionState>;
  onToggleSelection: (photoId: string) => void;
}

type PhotoFaceDetailPayload = {
  photo_id: string;
  faces: FaceBBoxOverlayFace[];
};

const INGEST_STATUS_LEGEND_TOOLTIP = INGEST_STATUS_LEGEND
  .map((entry) => `${entry.label}: ${entry.description}`)
  .join("\n");

export function LibraryPhotoGrid({
  photos,
  showAllFaceBoxes,
  selectedPhotoIds,
  locationSearch,
  selectionRouteState,
  onToggleSelection
}: LibraryPhotoGridProps) {
  const [photoFaceBoxVisibility, setPhotoFaceBoxVisibility] = useState<Record<string, boolean>>({});
  const [photoFaceDetails, setPhotoFaceDetails] = useState<Record<string, PhotoFaceDetailPayload | null>>({});
  const [photoFaceDetailStatus, setPhotoFaceDetailStatus] = useState<
    Record<string, "loading" | "loaded" | "failed">
  >({});

  const activeFaceOverlayPhotoIds = useMemo(
    () =>
      photos
        .filter((photo) => {
          const hasDetectedFaces = (photo.faces?.length ?? 0) > 0;
          const hasThumbnail = Boolean(photo.thumbnail);
          const isRequested = showAllFaceBoxes || Boolean(photoFaceBoxVisibility[photo.photo_id]);
          return hasDetectedFaces && hasThumbnail && isRequested;
        })
        .map((photo) => photo.photo_id),
    [photos, photoFaceBoxVisibility, showAllFaceBoxes]
  );

  useEffect(() => {
    const controller = new AbortController();

    activeFaceOverlayPhotoIds.forEach((photoId) => {
      if (photoFaceDetailStatus[photoId]) {
        return;
      }

      setPhotoFaceDetailStatus((current) => ({ ...current, [photoId]: "loading" }));

      fetch(`/api/v1/photos/${photoId}`, { signal: controller.signal })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`Photo detail request failed (${response.status})`);
          }
          const payload = (await response.json()) as PhotoFaceDetailPayload;
          setPhotoFaceDetails((current) => ({ ...current, [photoId]: payload }));
          setPhotoFaceDetailStatus((current) => ({ ...current, [photoId]: "loaded" }));
        })
        .catch(() => {
          if (controller.signal.aborted) {
            return;
          }
          setPhotoFaceDetails((current) => ({ ...current, [photoId]: null }));
          setPhotoFaceDetailStatus((current) => ({ ...current, [photoId]: "failed" }));
        });
    });

    return () => {
      controller.abort();
    };
  }, [activeFaceOverlayPhotoIds, photoFaceDetailStatus]);

  return (
    <ol className="browse-grid" aria-label="Photo gallery">
      {photos.map((photo) => {
        const ingestStatus = deriveIngestStatus({
          availabilityState: photo.original?.availability_state ?? null,
          isAvailable: photo.original?.is_available ?? null,
          lastFailureReason: photo.original?.last_failure_reason ?? null,
          hasThumbnail: Boolean(photo.thumbnail)
        });
        const hasDetectedFaces = (photo.faces?.length ?? 0) > 0;
        const showFaceBoxesForPhoto =
          hasDetectedFaces && (showAllFaceBoxes || Boolean(photoFaceBoxVisibility[photo.photo_id]));
        const detailPayload = photoFaceDetails[photo.photo_id] ?? null;
        const overlayRegions =
          showFaceBoxesForPhoto && photo.thumbnail && detailPayload
            ? buildFaceOverlayRegions(
                detailPayload.faces,
                photo.thumbnail.width,
                photo.thumbnail.height
              )
            : [];

        return (
          <li key={photo.photo_id} className="browse-card">
            <p className="browse-ingest-status">
              <span
                className={`ingest-status-badge is-${ingestStatus.tone}`}
                title={INGEST_STATUS_LEGEND_TOOLTIP}
                aria-label={`Ingest status ${ingestStatus.label}. Hover for full status legend.`}
              >
                {ingestStatus.label}
              </span>
            </p>
            <label className="browse-card-selection">
              <input
                type="checkbox"
                checked={selectedPhotoIds.has(photo.photo_id)}
                onChange={() => onToggleSelection(photo.photo_id)}
              />
              Select photo
            </label>
            <label className="browse-card-face-box-toggle">
              <input
                type="checkbox"
                aria-label={`Show face boxes for ${photo.photo_id}`}
                checked={showFaceBoxesForPhoto}
                disabled={!hasDetectedFaces || showAllFaceBoxes}
                onChange={(event) => {
                  const nextChecked = event.currentTarget.checked;
                  setPhotoFaceBoxVisibility((current) => ({
                    ...current,
                    [photo.photo_id]: nextChecked
                  }));
                }}
              />
              Show face boxes
            </label>
            {photo.thumbnail ? (
              <Link
                className="browse-thumbnail-link"
                data-photo-id={photo.photo_id}
                to={`/library/${photo.photo_id}`}
                state={{
                  returnToLibrarySearch: locationSearch,
                  returnFocusPhotoId: photo.photo_id,
                  librarySelection: selectionRouteState
                }}
                aria-label={`View details for ${photo.path}`}
              >
                <img
                  className="browse-thumbnail"
                  src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                  width={photo.thumbnail.width}
                  height={photo.thumbnail.height}
                  alt={`Preview of ${photo.path}`}
                />
                <FaceBBoxOverlay
                  regions={overlayRegions}
                  ariaLabel={`Detected face regions for ${photo.photo_id}`}
                />
              </Link>
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
                    View details
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

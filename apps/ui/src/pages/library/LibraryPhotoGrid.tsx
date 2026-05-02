import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../../app/ingestStatus";
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

type FaceLabelSource = "human_confirmed" | "machine_applied" | "machine_suggested" | null;

type FaceBBox = {
  face_id: string;
  person_id: string | null;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
  label_source?: FaceLabelSource;
};

type PhotoFaceDetailPayload = {
  photo_id: string;
  faces: FaceBBox[];
};

type FaceOverlayRegion = {
  faceId: string;
  personId: string | null;
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
};

const INGEST_STATUS_LEGEND_TOOLTIP = INGEST_STATUS_LEGEND
  .map((entry) => `${entry.label}: ${entry.description}`)
  .join("\n");

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function inferFaceOverlayCoordinateSpace(
  faces: FaceBBox[],
  thumbnailWidth: number,
  thumbnailHeight: number
): { width: number; height: number } {
  const coordinateSpace = faces.reduce(
    (acc, face) => {
      if (
        face.bbox_x === null ||
        face.bbox_y === null ||
        face.bbox_w === null ||
        face.bbox_h === null ||
        face.bbox_w <= 0 ||
        face.bbox_h <= 0
      ) {
        return acc;
      }

      acc.width = Math.max(acc.width, face.bbox_x + face.bbox_w);
      acc.height = Math.max(acc.height, face.bbox_y + face.bbox_h);
      return acc;
    },
    { width: thumbnailWidth, height: thumbnailHeight }
  );

  return {
    width: Math.max(coordinateSpace.width, thumbnailWidth),
    height: Math.max(coordinateSpace.height, thumbnailHeight)
  };
}

function buildOverlayRegions(
  faces: FaceBBox[],
  thumbnailWidth: number,
  thumbnailHeight: number
): FaceOverlayRegion[] {
  if (thumbnailWidth <= 0 || thumbnailHeight <= 0) {
    return [];
  }

  const coordinateSpace = inferFaceOverlayCoordinateSpace(faces, thumbnailWidth, thumbnailHeight);

  return faces
    .map((face) => {
      if (
        face.bbox_x === null ||
        face.bbox_y === null ||
        face.bbox_w === null ||
        face.bbox_h === null ||
        face.bbox_w <= 0 ||
        face.bbox_h <= 0
      ) {
        return null;
      }

      const left = clamp((face.bbox_x / coordinateSpace.width) * 100, 0, 100);
      const top = clamp((face.bbox_y / coordinateSpace.height) * 100, 0, 100);
      const right = clamp(((face.bbox_x + face.bbox_w) / coordinateSpace.width) * 100, 0, 100);
      const bottom = clamp(((face.bbox_y + face.bbox_h) / coordinateSpace.height) * 100, 0, 100);
      const width = right - left;
      const height = bottom - top;

      if (width <= 0 || height <= 0) {
        return null;
      }

      return {
        faceId: face.face_id,
        personId: face.person_id,
        leftPercent: left,
        topPercent: top,
        widthPercent: width,
        heightPercent: height
      };
    })
    .filter((region): region is FaceOverlayRegion => region !== null);
}

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
            ? buildOverlayRegions(
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
                {overlayRegions.length > 0 ? (
                  <ol
                    className="detail-face-overlay-list"
                    aria-label={`Detected face regions for ${photo.photo_id}`}
                  >
                    {overlayRegions.map((region, index) => (
                      <li
                        key={region.faceId}
                        className="detail-face-overlay"
                        aria-label={`Face region ${index + 1}${region.personId ? ` for ${region.personId}` : ""}`}
                        style={{
                          left: `${region.leftPercent}%`,
                          top: `${region.topPercent}%`,
                          width: `${region.widthPercent}%`,
                          height: `${region.heightPercent}%`
                        }}
                      />
                    ))}
                  </ol>
                ) : null}
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

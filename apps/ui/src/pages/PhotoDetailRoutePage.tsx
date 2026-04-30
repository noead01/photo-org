import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../app/ingestStatus";
import {
  resolveDetailReturnState,
  setPendingBrowseFocusPhotoId
} from "./browseFocusState";

type PhotoDetailPayload = {
  photo_id: string;
  path: string;
  ext: string;
  camera_make: string | null;
  orientation: string | null;
  shot_ts: string | null;
  filesize: number;
  tags: string[];
  people: string[];
  faces: Array<{
    face_id: string;
    person_id: string | null;
    bbox_x: number | null;
    bbox_y: number | null;
    bbox_w: number | null;
    bbox_h: number | null;
  }>;
  thumbnail: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
  original: {
    is_available: boolean;
    availability_state: string;
    last_failure_reason: string | null;
  } | null;
  metadata: {
    sha256: string;
    phash: string | null;
    shot_ts_source: string | null;
    camera_model: string | null;
    software: string | null;
    gps_latitude: number | null;
    gps_longitude: number | null;
    gps_altitude: number | null;
    created_ts: string;
    updated_ts: string;
    modified_ts: string | null;
    deleted_ts: string | null;
    faces_count: number;
    faces_detected_ts: string | null;
  };
};

const MISSING_VALUE = "Not available";

type MediaPresentationMode = "fit" | "actual";

type FaceOverlayRegion = {
  faceId: string;
  personId: string | null;
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
};

class PhotoDetailRequestError extends Error {
  status: number;

  constructor(status: number) {
    super(`Photo detail request failed (${status})`);
    this.status = status;
    this.name = "PhotoDetailRequestError";
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return MISSING_VALUE;
  }

  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC"
  }).format(parsed);
}

function formatFilesize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

function formatGps(lat: number | null, lon: number | null): string {
  if (lat === null || lon === null) {
    return MISSING_VALUE;
  }

  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
}

function formatOptionalText(value: string | null): string {
  return value && value.trim().length > 0 ? value : MISSING_VALUE;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

async function fetchPhotoDetail(photoId: string): Promise<PhotoDetailPayload> {
  const response = await fetch(`/api/v1/photos/${photoId}`);
  if (!response.ok) {
    throw new PhotoDetailRequestError(response.status);
  }
  return (await response.json()) as PhotoDetailPayload;
}

export function PhotoDetailRoutePage() {
  const location = useLocation();
  const { photoId } = useParams<{ photoId: string }>();
  const returnState = resolveDetailReturnState(location.state);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const [detail, setDetail] = useState<PhotoDetailPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const [mediaMode, setMediaMode] = useState<MediaPresentationMode>("fit");

  useEffect(() => {
    headingRef.current?.focus();
  }, [photoId]);

  useEffect(() => {
    if (!photoId) {
      setError("Photo identifier is missing.");
      setIsNotFound(false);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    setIsNotFound(false);

    fetchPhotoDetail(photoId)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }
        setIsNotFound(false);
        setDetail(payload);
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        if (caughtError instanceof PhotoDetailRequestError && caughtError.status === 404) {
          setDetail(null);
          setError(null);
          setIsNotFound(true);
          setIsLoading(false);
          return;
        }

        setError(caughtError instanceof Error ? caughtError.message : "Could not load photo detail.");
        setIsNotFound(false);
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [photoId, reloadToken]);

  const facesLabel = useMemo(() => {
    if (!detail) {
      return MISSING_VALUE;
    }
    const count = detail.metadata.faces_count;
    return count === 1 ? "1 detected" : `${count} detected`;
  }, [detail]);

  const faceOverlayRegions = useMemo<FaceOverlayRegion[]>(() => {
    if (!detail?.thumbnail || detail.thumbnail.width <= 0 || detail.thumbnail.height <= 0) {
      return [];
    }

    const thumbnailWidth = detail.thumbnail.width;
    const thumbnailHeight = detail.thumbnail.height;

    return detail.faces
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

        const left = clamp((face.bbox_x / thumbnailWidth) * 100, 0, 100);
        const top = clamp((face.bbox_y / thumbnailHeight) * 100, 0, 100);
        const right = clamp(((face.bbox_x + face.bbox_w) / thumbnailWidth) * 100, 0, 100);
        const bottom = clamp(((face.bbox_y + face.bbox_h) / thumbnailHeight) * 100, 0, 100);
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
  }, [detail]);

  const faceRegionState = useMemo(() => {
    if (!detail) {
      return MISSING_VALUE;
    }

    if (detail.faces.length === 0) {
      return "No face regions detected for this photo.";
    }

    if (faceOverlayRegions.length === 0) {
      return "Face regions are present but could not be rendered on this preview.";
    }

    return `${faceOverlayRegions.length} face region${faceOverlayRegions.length === 1 ? "" : "s"} rendered.`;
  }, [detail, faceOverlayRegions.length]);

  const ingestStatus = useMemo(() => {
    if (!detail) {
      return null;
    }
    return deriveIngestStatus({
      availabilityState: detail.original?.availability_state ?? null,
      isAvailable: detail.original?.is_available ?? null,
      lastFailureReason: detail.original?.last_failure_reason ?? null,
      hasThumbnail: Boolean(detail.thumbnail),
      includeFaceDetection: true,
      facesDetectedTs: detail.metadata.faces_detected_ts
    });
  }, [detail]);

  const backLinkFocusPhotoId = detail?.photo_id ?? returnState.returnFocusPhotoId ?? photoId ?? null;

  return (
    <section aria-labelledby="page-title" className="page detail-page">
      <div className="detail-header">
        <div>
          <h1 id="page-title" ref={headingRef} tabIndex={-1}>
            Photo detail
          </h1>
          <p>Inspect canonical metadata and availability fields for a single photo.</p>
        </div>
        <Link
          className="detail-back-link"
          to={{
            pathname: "/browse",
            search: returnState.returnToBrowseSearch ?? ""
          }}
          state={backLinkFocusPhotoId ? { restoreFocusPhotoId: backLinkFocusPhotoId } : undefined}
          onClick={() => {
            if (backLinkFocusPhotoId) {
              setPendingBrowseFocusPhotoId(backLinkFocusPhotoId);
            }
          }}
        >
          Back to browse
        </Link>
      </div>
      <section className="status-legend" aria-label="Ingest status legend">
        <h2>Ingest status legend</h2>
        <ul>
          {INGEST_STATUS_LEGEND.map((entry) => (
            <li key={entry.tone}>
              <span className={`ingest-status-badge is-${entry.tone}`}>{entry.label}</span>
              <span>{entry.description}</span>
            </li>
          ))}
        </ul>
      </section>

      {isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading photo detail.
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load photo detail</h2>
          <p>{error}</p>
          <button type="button" onClick={() => setReloadToken((current) => current + 1)}>
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !error && detail ? (
        <div className="detail-layout">
          <article className="detail-panel">
            <h2>Preview</h2>
            {detail.thumbnail ? (
              <>
                <div className="detail-media-controls" role="group" aria-label="Preview display mode">
                  <button
                    type="button"
                    className={mediaMode === "fit" ? "is-active" : undefined}
                    onClick={() => setMediaMode("fit")}
                  >
                    Fit to panel
                  </button>
                  <button
                    type="button"
                    className={mediaMode === "actual" ? "is-active" : undefined}
                    onClick={() => setMediaMode("actual")}
                  >
                    Actual pixels
                  </button>
                </div>
                <div className="detail-media-frame" data-mode={mediaMode}>
                  <div className="detail-media-stage">
                    <img
                      className="detail-media-image"
                      src={`data:${detail.thumbnail.mime_type};base64,${detail.thumbnail.data_base64}`}
                      width={detail.thumbnail.width}
                      height={detail.thumbnail.height}
                      alt={`Preview for ${detail.photo_id}`}
                    />
                    {faceOverlayRegions.length > 0 ? (
                      <ol className="detail-face-overlay-list" aria-label="Detected face regions">
                        {faceOverlayRegions.map((region, index) => (
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
                  </div>
                </div>
                <p className="detail-face-state">{faceRegionState}</p>
              </>
            ) : (
              <>
                <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                  No preview
                </div>
                <p className="detail-face-state">{faceRegionState}</p>
              </>
            )}
          </article>

          <article className="detail-panel">
            <h2>{detail.photo_id}</h2>
            <p className="detail-path">{detail.path}</p>
            <dl>
              <div>
                <dt>Captured</dt>
                <dd>{formatTimestamp(detail.shot_ts)}</dd>
              </div>
              <div>
                <dt>File size</dt>
                <dd>{formatFilesize(detail.filesize)}</dd>
              </div>
              <div>
                <dt>Camera make</dt>
                <dd>{formatOptionalText(detail.camera_make)}</dd>
              </div>
              <div>
                <dt>Orientation</dt>
                <dd>{formatOptionalText(detail.orientation)}</dd>
              </div>
              <div>
                <dt>Availability</dt>
                <dd>{detail.original?.availability_state ?? "Unknown availability"}</dd>
              </div>
              <div>
                <dt>Ingest status</dt>
                <dd>
                  {ingestStatus ? (
                    <span className={`ingest-status-badge is-${ingestStatus.tone}`}>{ingestStatus.label}</span>
                  ) : (
                    "Unknown"
                  )}
                </dd>
              </div>
            </dl>
            {ingestStatus ? <p className="detail-ingest-status-detail">{ingestStatus.description}</p> : null}
          </article>

          <article className="detail-panel">
            <h2>Metadata</h2>
            <dl>
              <div>
                <dt>SHA-256</dt>
                <dd>{detail.metadata.sha256}</dd>
              </div>
              <div>
                <dt>Perceptual hash</dt>
                <dd>{formatOptionalText(detail.metadata.phash)}</dd>
              </div>
              <div>
                <dt>Timestamp source</dt>
                <dd>{formatOptionalText(detail.metadata.shot_ts_source)}</dd>
              </div>
              <div>
                <dt>Camera model</dt>
                <dd>{formatOptionalText(detail.metadata.camera_model)}</dd>
              </div>
              <div>
                <dt>Software</dt>
                <dd>{formatOptionalText(detail.metadata.software)}</dd>
              </div>
              <div>
                <dt>GPS</dt>
                <dd>{formatGps(detail.metadata.gps_latitude, detail.metadata.gps_longitude)}</dd>
              </div>
              <div>
                <dt>GPS altitude</dt>
                <dd>
                  {detail.metadata.gps_altitude === null
                    ? MISSING_VALUE
                    : `${detail.metadata.gps_altitude.toFixed(1)} m`}
                </dd>
              </div>
              <div>
                <dt>Faces</dt>
                <dd>{facesLabel}</dd>
              </div>
              <div>
                <dt>Face detection run</dt>
                <dd>{formatTimestamp(detail.metadata.faces_detected_ts)}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatTimestamp(detail.metadata.created_ts)}</dd>
              </div>
              <div>
                <dt>Updated</dt>
                <dd>{formatTimestamp(detail.metadata.updated_ts)}</dd>
              </div>
              <div>
                <dt>Modified</dt>
                <dd>{formatTimestamp(detail.metadata.modified_ts)}</dd>
              </div>
            </dl>
          </article>

          <article className="detail-panel">
            <h2>Classification</h2>
            <dl>
              <div>
                <dt>Tags</dt>
                <dd>{detail.tags.length > 0 ? detail.tags.join(", ") : "No tags"}</dd>
              </div>
              <div>
                <dt>People</dt>
                <dd>{detail.people.length > 0 ? detail.people.join(", ") : "No recognized people"}</dd>
              </div>
            </dl>
          </article>
        </div>
      ) : null}

      {!isLoading && !error && isNotFound ? (
        <section className="feedback-panel" aria-labelledby="photo-not-found-title">
          <h2 id="photo-not-found-title">Photo not found</h2>
          <p>This photo is no longer available in the catalog.</p>
        </section>
      ) : null}
    </section>
  );
}

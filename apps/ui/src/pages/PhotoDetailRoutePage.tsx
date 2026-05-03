import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { deriveIngestStatus } from "../app/ingestStatus";
import {
  buildFaceOverlayRegions,
  FaceBBoxOverlay,
  type FaceOverlayRegion
} from "./FaceBBoxOverlay";
import { PhotoFaceAssignmentModal } from "./PhotoFaceAssignmentModal";
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
    bbox_space_width?: number | null;
    bbox_space_height?: number | null;
    label_source: "human_confirmed" | "machine_applied" | "machine_suggested" | null;
    confidence: number | null;
    model_version: string | null;
    provenance: Record<string, unknown> | null;
    label_recorded_ts: string | null;
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
    exif_attributes: Record<string, unknown> | null;
    created_ts: string;
    updated_ts: string;
    modified_ts: string | null;
    deleted_ts: string | null;
    faces_count: number;
    faces_detected_ts: string | null;
  };
};

const MISSING_VALUE = "Not available";
const EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS = 30;

type MediaPresentationMode = "fit" | "actual";

type PersonRecord = {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
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

function formatExifAttributeValue(value: unknown): string {
  const renderedValue = (() => {
    if (value === null) {
      return "null";
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  })();

  if (renderedValue.length <= EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS) {
    return renderedValue;
  }
  return `${renderedValue.slice(0, EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS)}...`;
}

async function fetchPhotoDetail(photoId: string): Promise<PhotoDetailPayload> {
  const response = await fetch(`/api/v1/photos/${photoId}`);
  if (!response.ok) {
    throw new PhotoDetailRequestError(response.status);
  }
  return (await response.json()) as PhotoDetailPayload;
}

function sortPeopleDirectory(people: PersonRecord[]): PersonRecord[] {
  return [...people].sort((left, right) => {
    const displayComparison = left.display_name.localeCompare(right.display_name, "en-US");
    if (displayComparison !== 0) {
      return displayComparison;
    }
    return left.person_id.localeCompare(right.person_id, "en-US");
  });
}

function derivePersonInitials(displayName: string | null): string {
  if (!displayName) {
    return "?";
  }
  const tokens = displayName
    .trim()
    .split(/\\s+/)
    .map((token) => token.replace(/[^a-zA-Z0-9]/g, ""))
    .filter((token) => token.length > 0);
  if (tokens.length === 0) {
    return "?";
  }
  if (tokens.length === 1) {
    const [token] = tokens;
    return token.slice(0, Math.min(2, token.length)).toUpperCase();
  }
  return `${tokens[0][0] ?? ""}${tokens[1][0] ?? ""}`.toUpperCase();
}

function resolveAbsoluteUrl(url: string): string {
  if (typeof window === "undefined") {
    return url;
  }
  return new URL(url, window.location.href).toString();
}

function revokeObjectUrl(url: string): void {
  if (typeof URL.revokeObjectURL === "function") {
    URL.revokeObjectURL(url);
  }
}

function isCurrentImageRequest(
  image: HTMLImageElement,
  expectedSrc: string
): boolean {
  const expectedAbsoluteSrc = resolveAbsoluteUrl(expectedSrc);
  const currentSrc = image.currentSrc;
  if (currentSrc && currentSrc.length > 0) {
    return currentSrc === expectedAbsoluteSrc;
  }
  const rawSrc = image.getAttribute("src");
  return rawSrc === expectedSrc || rawSrc === expectedAbsoluteSrc;
}

function applyFaceAssignment(
  detail: PhotoDetailPayload,
  faceId: string,
  personId: string
): PhotoDetailPayload {
  const nextFaces = detail.faces.map((face) =>
    face.face_id === faceId
      ? {
          ...face,
          person_id: personId,
          label_source: null,
          confidence: null,
          model_version: null,
          provenance: null,
          label_recorded_ts: null,
        }
      : face
  );
  const nextPeople = Array.from(
    new Set(
      nextFaces
        .map((face) => face.person_id)
        .filter((value): value is string => value !== null)
    )
  );

  return {
    ...detail,
    faces: nextFaces,
    people: nextPeople
  };
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
  const [mediaMode, setMediaMode] = useState<MediaPresentationMode>("actual");
  const [imageScalePercent, setImageScalePercent] = useState(100);
  const [isOriginalImageEnabled, setIsOriginalImageEnabled] = useState(true);
  const [originalImageRetrySrc, setOriginalImageRetrySrc] = useState<string | null>(null);
  const [originalImageNaturalSize, setOriginalImageNaturalSize] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const activePhotoIdRef = useRef<string | null>(null);
  const [showFaceBoxes, setShowFaceBoxes] = useState(true);
  const [isDetailFlyoutOpen, setIsDetailFlyoutOpen] = useState(false);
  const [isExifAttributesOpen, setIsExifAttributesOpen] = useState(false);
  const [activeFaceModalId, setActiveFaceModalId] = useState<string | null>(null);
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);

  useEffect(() => {
    headingRef.current?.focus();
  }, [photoId]);

  useEffect(() => {
    activePhotoIdRef.current = detail?.photo_id ?? null;
  }, [detail?.photo_id]);

  useEffect(() => {
    setIsOriginalImageEnabled(true);
    setOriginalImageNaturalSize(null);
    setIsExifAttributesOpen(false);
    setOriginalImageRetrySrc((current) => {
      if (current) {
        revokeObjectUrl(current);
      }
      return null;
    });
  }, [photoId]);

  useEffect(() => {
    return () => {
      if (originalImageRetrySrc) {
        revokeObjectUrl(originalImageRetrySrc);
      }
    };
  }, [originalImageRetrySrc]);

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

  useEffect(() => {
    const controller = new AbortController();

    fetch("/api/v1/people", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`People request failed (${response.status})`);
        }

        const payload = (await response.json()) as PersonRecord[];
        setPeopleDirectory(sortPeopleDirectory(payload));
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPeopleDirectory([]);
        }
      });

    return () => {
      controller.abort();
    };
  }, [reloadToken]);

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

    return buildFaceOverlayRegions(detail.faces, detail.thumbnail.width, detail.thumbnail.height);
  }, [detail]);

  const faceRegionState = useMemo(() => {
    if (!detail) {
      return MISSING_VALUE;
    }

    if (detail.faces.length === 0) {
      return "No face regions detected for this photo.";
    }

    if (!showFaceBoxes) {
      return "Face boxes are hidden for this preview.";
    }

    if (faceOverlayRegions.length === 0) {
      return "Face regions are present but could not be rendered on this preview.";
    }

    return `${faceOverlayRegions.length} face region${faceOverlayRegions.length === 1 ? "" : "s"} rendered.`;
  }, [detail, faceOverlayRegions.length, showFaceBoxes]);

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

  const peopleNameById = useMemo(() => {
    return new Map(peopleDirectory.map((person) => [person.person_id, person.display_name]));
  }, [peopleDirectory]);

  const faceBadgeInitialsById = useMemo(() => {
    return new Map(
      (detail?.faces ?? []).map((face) => [
        face.face_id,
        face.person_id ? derivePersonInitials(peopleNameById.get(face.person_id) ?? null) : "?"
      ])
    );
  }, [detail?.faces, peopleNameById]);

  const selectedFaceForModal = useMemo(() => {
    if (!detail || !activeFaceModalId) {
      return null;
    }
    const index = detail.faces.findIndex((face) => face.face_id === activeFaceModalId);
    if (index < 0) {
      return null;
    }
    return { ...detail.faces[index], sequence: index + 1 };
  }, [activeFaceModalId, detail]);

  const selectedRegionForModal = useMemo(() => {
    if (!activeFaceModalId) {
      return null;
    }
    return faceOverlayRegions.find((region) => region.faceId === activeFaceModalId) ?? null;
  }, [activeFaceModalId, faceOverlayRegions]);

  const exifAttributeEntries = useMemo(() => {
    const attributes = detail?.metadata.exif_attributes;
    if (!attributes) {
      return [] as Array<[string, unknown]>;
    }
    return Object.entries(attributes).sort(([leftName], [rightName]) =>
      leftName.localeCompare(rightName, "en-US")
    );
  }, [detail?.metadata.exif_attributes]);

  const backLinkFocusPhotoId = detail?.photo_id ?? returnState.returnFocusPhotoId ?? photoId ?? null;
  const mediaScale = imageScalePercent / 100;
  const thumbnailDataUrl = detail?.thumbnail
    ? `data:${detail.thumbnail.mime_type};base64,${detail.thumbnail.data_base64}`
    : null;
  const originalImageUrl = detail ? `/api/v1/photos/${encodeURIComponent(detail.photo_id)}/original` : null;
  const shouldUseOriginalImage = Boolean(originalImageUrl && isOriginalImageEnabled);
  const activeOriginalImageSrc = shouldUseOriginalImage ? (originalImageRetrySrc ?? originalImageUrl) : null;
  const previewImageSrc = activeOriginalImageSrc ?? thumbnailDataUrl;
  const mediaBaseWidthPx = shouldUseOriginalImage
    ? (originalImageNaturalSize?.width ?? null)
    : (detail?.thumbnail?.width ?? null);
  const mediaStageStyle: CSSProperties = mediaMode === "fit"
    ? { width: `${Math.max(25, imageScalePercent)}%` }
    : {
        width:
          mediaBaseWidthPx !== null
            ? `${Math.max(80, Math.round(mediaBaseWidthPx * mediaScale))}px`
            : "auto"
      };

  function handleFaceAssigned(faceId: string, personId: string) {
    setDetail((current) => (current ? applyFaceAssignment(current, faceId, personId) : current));
  }

  function handlePersonCreated(person: {
    person_id: string;
    display_name: string;
    created_ts?: string;
    updated_ts?: string;
  }) {
    setPeopleDirectory((current) => {
      if (current.some((candidate) => candidate.person_id === person.person_id)) {
        return current;
      }
      return sortPeopleDirectory([
        ...current,
        {
          person_id: person.person_id,
          display_name: person.display_name,
          created_ts: person.created_ts ?? new Date().toISOString(),
          updated_ts: person.updated_ts ?? new Date().toISOString()
        }
      ]);
    });
  }

  function openFaceAssignmentModal(faceId: string) {
    setActiveFaceModalId(faceId);
  }

  async function retryOriginalImageThroughBlob(url: string, expectedPhotoId: string): Promise<boolean> {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        return false;
      }
      const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
      if (!contentType.startsWith("image/")) {
        return false;
      }
      const blob = await response.blob();
      if (blob.size <= 0) {
        return false;
      }
      if (activePhotoIdRef.current !== expectedPhotoId) {
        return false;
      }
      if (typeof URL.createObjectURL !== "function") {
        return false;
      }
      const objectUrl = URL.createObjectURL(blob);
      setOriginalImageRetrySrc((current) => {
        if (current) {
          revokeObjectUrl(current);
        }
        return objectUrl;
      });
      return true;
    } catch {
      return false;
    }
  }

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
            pathname: "/library",
            search: returnState.returnToLibrarySearch ?? ""
          }}
          state={
            backLinkFocusPhotoId || returnState.librarySelection
              ? {
                  restoreFocusPhotoId: backLinkFocusPhotoId ?? undefined,
                  librarySelection: returnState.librarySelection
                }
              : undefined
          }
          onClick={() => {
            if (backLinkFocusPhotoId) {
              setPendingBrowseFocusPhotoId(backLinkFocusPhotoId);
            }
          }}
        >
          Back to library
        </Link>
      </div>
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
        <div className="detail-workspace">
          <article className="detail-preview-panel">
            <h2>Preview</h2>
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
              <label className="detail-face-box-toggle">
                <input
                  type="checkbox"
                  aria-label="Show face boxes"
                  checked={showFaceBoxes}
                  onChange={(event) => setShowFaceBoxes(event.currentTarget.checked)}
                />
                Show face boxes
              </label>
              <label className="detail-photo-scale">
                <span>Photo size</span>
                <input
                  type="range"
                  min={25}
                  max={225}
                  step={5}
                  value={imageScalePercent}
                  aria-label="Photo size"
                  onChange={(event) => setImageScalePercent(Number(event.currentTarget.value))}
                />
                <span>{imageScalePercent}%</span>
              </label>
              <button
                type="button"
                onClick={() => {
                  setIsDetailFlyoutOpen((current) => !current);
                }}
              >
                {isDetailFlyoutOpen ? "Hide details" : "Show details"}
              </button>
            </div>
            {ingestStatus ? (
              <p className="detail-ingest-inline">
                <span className={`ingest-status-badge is-${ingestStatus.tone}`}>{ingestStatus.label}</span>
                <span>{ingestStatus.description}</span>
              </p>
            ) : null}
            {previewImageSrc ? (
              <div className="detail-media-frame" data-mode={mediaMode}>
                <div className="detail-media-stage" style={mediaStageStyle}>
                  <img
                    className="detail-media-image"
                    src={previewImageSrc}
                    width={!shouldUseOriginalImage ? detail.thumbnail?.width : undefined}
                    height={!shouldUseOriginalImage ? detail.thumbnail?.height : undefined}
                    alt={`Preview for ${detail.photo_id}`}
                    onLoad={(event) => {
                      if (
                        !shouldUseOriginalImage
                        || !activeOriginalImageSrc
                        || !isCurrentImageRequest(event.currentTarget, activeOriginalImageSrc)
                      ) {
                        return;
                      }
                      const { naturalWidth, naturalHeight } = event.currentTarget;
                      if (naturalWidth > 0 && naturalHeight > 0) {
                        setOriginalImageNaturalSize({ width: naturalWidth, height: naturalHeight });
                      }
                    }}
                    onError={(event) => {
                      if (
                        !shouldUseOriginalImage
                        || !activeOriginalImageSrc
                        || !isCurrentImageRequest(event.currentTarget, activeOriginalImageSrc)
                      ) {
                        return;
                      }
                      if (!originalImageRetrySrc && originalImageUrl && detail) {
                        void retryOriginalImageThroughBlob(originalImageUrl, detail.photo_id).then((recovered) => {
                          if (recovered) {
                            return;
                          }
                          setIsOriginalImageEnabled(false);
                          setOriginalImageNaturalSize(null);
                        });
                        return;
                      }
                      setIsOriginalImageEnabled(false);
                      setOriginalImageNaturalSize(null);
                    }}
                  />
                  {showFaceBoxes ? (
                    <FaceBBoxOverlay
                      regions={faceOverlayRegions}
                      ariaLabel="Detected face regions"
                      onRegionClick={(region) => {
                        openFaceAssignmentModal(region.faceId);
                      }}
                      renderRegionContent={(region, index) => (
                        <button
                          type="button"
                          className="detail-face-overlay-provenance-button"
                          aria-label={`Open face assignment for face region ${index + 1}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            openFaceAssignmentModal(region.faceId);
                          }}
                        >
                          {faceBadgeInitialsById.get(region.faceId) ?? "?"}
                        </button>
                      )}
                    />
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                No preview
              </div>
            )}
            <p className="detail-face-state">{faceRegionState}</p>
          </article>

          <button
            type="button"
            className={`detail-flyout-backdrop${isDetailFlyoutOpen ? " is-open" : ""}`}
            aria-label="Hide details flyout"
            onClick={() => setIsDetailFlyoutOpen(false)}
          />

          <aside
            className={`detail-flyout${isDetailFlyoutOpen ? " is-open" : ""}`}
            aria-label="Photo details flyout"
          >
            <div className="detail-flyout-header">
              <h2>{detail.photo_id}</h2>
              <button type="button" onClick={() => setIsDetailFlyoutOpen(false)}>
                Close
              </button>
            </div>
            <p className="detail-path">{detail.path}</p>

            <article className="detail-panel">
              <h2>Summary</h2>
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
              {exifAttributeEntries.length > 0 ? (
                <section className="detail-exif-attributes">
                  <button
                    type="button"
                    className="detail-exif-attributes-toggle"
                    aria-expanded={isExifAttributesOpen}
                    aria-controls="detail-exif-attributes-list"
                    onClick={() => setIsExifAttributesOpen((current) => !current)}
                  >
                    {isExifAttributesOpen ? "Hide all EXIF attributes" : "Show all EXIF attributes"}
                  </button>
                  {isExifAttributesOpen ? (
                    <dl id="detail-exif-attributes-list" className="detail-exif-attributes-list">
                      {exifAttributeEntries.map(([attributeName, attributeValue]) => (
                        <div key={attributeName}>
                          <dt>{attributeName}</dt>
                          <dd>{formatExifAttributeValue(attributeValue)}</dd>
                        </div>
                      ))}
                    </dl>
                  ) : null}
                </section>
              ) : null}
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
          </aside>
        </div>
      ) : null}

      {!isLoading && !error && isNotFound ? (
        <section className="feedback-panel" aria-labelledby="photo-not-found-title">
          <h2 id="photo-not-found-title">Photo not found</h2>
          <p>This photo is no longer available in the catalog.</p>
        </section>
      ) : null}

      <PhotoFaceAssignmentModal
        isOpen={selectedFaceForModal !== null}
        face={selectedFaceForModal}
        region={selectedRegionForModal}
        thumbnail={detail?.thumbnail ?? null}
        people={peopleDirectory.map((person) => ({
          person_id: person.person_id,
          display_name: person.display_name,
          created_ts: person.created_ts,
          updated_ts: person.updated_ts
        }))}
        onClose={() => setActiveFaceModalId(null)}
        onFaceUpdated={handleFaceAssigned}
        onPersonCreated={handlePersonCreated}
      />
    </section>
  );
}

import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

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

async function fetchPhotoDetail(photoId: string): Promise<PhotoDetailPayload> {
  const response = await fetch(`/api/v1/photos/${photoId}`);
  if (!response.ok) {
    throw new Error(`Photo detail request failed (${response.status})`);
  }
  return (await response.json()) as PhotoDetailPayload;
}

export function PhotoDetailRoutePage() {
  const { photoId } = useParams<{ photoId: string }>();
  const [detail, setDetail] = useState<PhotoDetailPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!photoId) {
      setError("Photo identifier is missing.");
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);

    fetchPhotoDetail(photoId)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }
        setDetail(payload);
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setError(caughtError instanceof Error ? caughtError.message : "Could not load photo detail.");
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

  return (
    <section aria-labelledby="page-title" className="page detail-page">
      <div className="detail-header">
        <div>
          <h1 id="page-title">Photo detail</h1>
          <p>Inspect canonical metadata and availability fields for a single photo.</p>
        </div>
        <Link className="detail-back-link" to="/browse">
          Back to browse
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
        <div className="detail-layout">
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
            </dl>
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
    </section>
  );
}

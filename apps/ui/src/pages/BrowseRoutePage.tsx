import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import type { NotificationEntry } from "../app/feedback/feedbackTypes";
import { ToastStack } from "../app/feedback/ToastStack";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../app/ingestStatus";

type SortDirection = "asc" | "desc";

type BrowsePhoto = {
  photo_id: string;
  path: string;
  ext: string;
  camera_make: string | null;
  orientation: string | null;
  shot_ts: string | null;
  filesize: number;
  tags: string[];
  people: string[];
  faces: Array<{ person_id: string | null }>;
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
  relevance: number | null;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    items: BrowsePhoto[];
    cursor: string | null;
  };
};

const PAGE_LIMIT = 24;
const INVALID_PAGE_MESSAGE = "Reset to page 1 because that page position is unavailable.";

function formatShotTimestamp(shotTs: string | null): string {
  if (!shotTs) {
    return "Unknown capture time";
  }

  const timestamp = Date.parse(shotTs);
  if (Number.isNaN(timestamp)) {
    return shotTs;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC"
  }).format(timestamp);
}

function formatFilesize(filesize: number): string {
  if (filesize < 1024) {
    return `${filesize} B`;
  }

  const kb = filesize / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

async function fetchBrowsePage(
  sortDirection: SortDirection,
  cursor: string | null
): Promise<SearchResponsePayload> {
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      sort: {
        by: "shot_ts",
        dir: sortDirection
      },
      page: {
        limit: PAGE_LIMIT,
        cursor
      }
    })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

function parseRequestedPage(search: string): number {
  const rawPage = new URLSearchParams(search).get("page");
  if (!rawPage) {
    return 1;
  }

  const parsedPage = Number.parseInt(rawPage, 10);
  if (!Number.isFinite(parsedPage) || parsedPage < 1) {
    return 1;
  }

  return parsedPage;
}

export function BrowseRoutePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const requestedPage = parseRequestedPage(location.search);

  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [cursorByPage, setCursorByPage] = useState<Record<number, string | null>>({ 1: null });
  const [photos, setPhotos] = useState<BrowsePhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);

  const cursorForPage = cursorByPage[requestedPage];

  function setPage(pageNumber: number, replace = false) {
    const nextParams = new URLSearchParams(location.search);
    if (pageNumber <= 1) {
      nextParams.delete("page");
    } else {
      nextParams.set("page", String(pageNumber));
    }

    const nextSearch = nextParams.toString();
    const nextTarget = `${location.pathname}${nextSearch ? `?${nextSearch}` : ""}`;
    const currentTarget = `${location.pathname}${location.search}`;

    if (nextTarget !== currentTarget) {
      navigate(nextTarget, { replace });
    }
  }

  function pushWarning(message: string) {
    setNotifications((current) => [
      {
        id: "browse-warning",
        tone: "warning",
        message
      },
      ...current.filter((entry) => entry.id !== "browse-warning")
    ]);
  }

  useEffect(() => {
    if (requestedPage > 1 && cursorForPage === undefined) {
      pushWarning(INVALID_PAGE_MESSAGE);
      setPage(1, true);
      return;
    }

    const controller = new AbortController();

    setIsLoading(true);
    setError(null);

    fetchBrowsePage(sortDirection, cursorForPage ?? null)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }

        if (requestedPage > 1 && payload.hits.items.length === 0) {
          pushWarning(INVALID_PAGE_MESSAGE);
          setPage(1, true);
          return;
        }

        setPhotos(payload.hits.items);
        setTotalCount(payload.hits.total);
        setNextCursor(payload.hits.cursor);
        setCursorByPage((current) => {
          const next = { ...current, [requestedPage]: cursorForPage ?? null };
          if (payload.hits.cursor === null) {
            delete next[requestedPage + 1];
          } else {
            next[requestedPage + 1] = payload.hits.cursor;
          }
          return next;
        });
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        const message =
          caughtError instanceof Error
            ? caughtError.message
            : "Could not load browse results.";
        setError(message);
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [cursorForPage, reloadToken, requestedPage, sortDirection]);

  const canGoPrevious = requestedPage > 1 && !isLoading;
  const canGoNext = nextCursor !== null && !isLoading;

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return `Loading page ${requestedPage}…`;
    }
    if (error) {
      return "Browse results unavailable.";
    }
    return `Showing ${photos.length} of ${totalCount} photos`;
  }, [error, isLoading, photos.length, requestedPage, totalCount]);

  return (
    <section aria-labelledby="page-title" className="page browse-page">
      <div className="browse-header">
        <div>
          <h1 id="page-title">Browse</h1>
          <p>Deterministic gallery ordering with stable cursor pagination.</p>
        </div>
        <div className="browse-controls" role="group" aria-label="Browse controls">
          <label className="browse-sort-control">
            Sort order
            <select
              aria-label="Sort order"
              value={sortDirection}
              onChange={(event) => {
                const nextDirection = event.target.value === "asc" ? "asc" : "desc";
                setSortDirection(nextDirection);
                setCursorByPage({ 1: null });
                setPage(1);
              }}
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </label>
          <div className="browse-pagination" aria-label="Pagination controls">
            <button
              type="button"
              onClick={() => setPage(requestedPage - 1)}
              disabled={!canGoPrevious}
              aria-label="Previous page"
            >
              Previous
            </button>
            <p className="browse-page-indicator">Page {requestedPage}</p>
            <button
              type="button"
              onClick={() => setPage(requestedPage + 1)}
              disabled={!canGoNext}
              aria-label="Next page"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      <p className="browse-summary" aria-live="polite">{summaryLabel}</p>
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

      {error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load Browse</h2>
          <p>{error}</p>
          <button type="button" onClick={() => setReloadToken((current) => current + 1)}>
            Retry
          </button>
        </div>
      ) : null}

      {!error && isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading browse workflow.
        </div>
      ) : null}

      {!error && !isLoading && photos.length === 0 ? (
        <div className="feedback-panel">
          <p>No photos available for this page.</p>
        </div>
      ) : null}

      {!error && !isLoading && photos.length > 0 ? (
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
                  <span className={`ingest-status-badge is-${ingestStatus.tone}`}>{ingestStatus.label}</span>
                  <span className="browse-ingest-status-detail">{ingestStatus.description}</span>
                </p>
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
                <h2>
                  <Link className="browse-photo-link" to={`/browse/${photo.photo_id}`}>
                    {photo.photo_id}
                  </Link>
                </h2>
                <p className="browse-path" title={photo.path}>{photo.path}</p>
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
                    <dd>{photo.people.length}</dd>
                  </div>
                  <div>
                    <dt>Original</dt>
                    <dd>{photo.original?.availability_state ?? "unknown"}</dd>
                  </div>
                </dl>
              </div>
              </li>
            );
          })}
        </ol>
      ) : null}

      <ToastStack
        notifications={notifications}
        onDismiss={(id) => {
          setNotifications((current) => current.filter((entry) => entry.id !== id));
        }}
      />
    </section>
  );
}

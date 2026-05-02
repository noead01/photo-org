import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { FeedbackSurface } from "../app/feedback/FeedbackSurface";
import type { FeedbackViewState, NotificationEntry } from "../app/feedback/feedbackTypes";
import { deriveIngestStatus, INGEST_STATUS_LEGEND } from "../app/ingestStatus";
import { PhotoResultIdentity } from "./library/PhotoResultIdentity";
import {
  INVALID_PAGE_MESSAGE,
  updateCursorByPage
} from "./library/pagination";
import { useRouteRequestState } from "./library/requestLifecycle";
import { parsePositiveIntParam } from "./library/urlSerialization";
import {
  createLibrarySelectionState,
  formatSelectionScopeLabel,
  librarySelectionReducer,
  parseLibrarySelectionRouteState,
  resolveSelectionScopeCount,
  serializeLibrarySelectionState
} from "./library/librarySelection";
import {
  consumePendingBrowseFocusPhotoId,
  resolveBrowseReturnState,
  setPendingBrowseFocusPhotoId
} from "./browseFocusState";

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
const BROWSE_FILTER_FINGERPRINT = "browse:all-results";

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

export function BrowseRoutePage() {
  const location = useLocation();
  const navigate = useNavigate();
  const requestedPage = parsePositiveIntParam(location.search, "page");
  const initialReturnState = resolveBrowseReturnState(location.state);

  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [cursorByPage, setCursorByPage] = useState<Record<number, string | null>>({ 1: null });
  const [photos, setPhotos] = useState<BrowsePhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);
  const [selectionState, dispatchSelection] = useReducer(
    librarySelectionReducer,
    initialReturnState?.librarySelection ?? null,
    createLibrarySelectionState
  );
  const {
    isLoading,
    error,
    reloadToken,
    beginRequest,
    completeRequest,
    failRequest,
    requestRetry
  } = useRouteRequestState();
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const pendingReturnFocusPhotoIdRef = useRef<string | null>(
    initialReturnState?.restoreFocusPhotoId ?? consumePendingBrowseFocusPhotoId()
  );
  const selectionRouteState = useMemo(
    () => serializeLibrarySelectionState(selectionState),
    [selectionState]
  );

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
    dispatchSelection({
      type: "filtersChanged",
      activeFilterFingerprint: BROWSE_FILTER_FINGERPRINT
    });
  }, []);

  useEffect(() => {
    const currentRouteSelection = parseLibrarySelectionRouteState(
      isRecord(location.state) ? location.state.browseSelection : undefined
    );

    if (areSelectionRouteStatesEqual(currentRouteSelection, selectionRouteState)) {
      return;
    }

    const routeState = isRecord(location.state) ? location.state : {};
    navigate(
      {
        pathname: location.pathname,
        search: location.search
      },
      {
        replace: true,
        state: {
          ...routeState,
          browseSelection: selectionRouteState
        }
      }
    );
  }, [
    location.pathname,
    location.search,
    location.state,
    navigate,
    selectionRouteState
  ]);

  useEffect(() => {
    if (requestedPage > 1 && cursorForPage === undefined) {
      pushWarning(INVALID_PAGE_MESSAGE);
      setPage(1, true);
      return;
    }

    const controller = new AbortController();

    beginRequest();

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
          return updateCursorByPage(
            current,
            requestedPage,
            cursorForPage ?? null,
            payload.hits.cursor
          );
        });
        completeRequest();
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        failRequest(caughtError, "Could not load browse results.");
      });

    return () => {
      controller.abort();
    };
  }, [cursorForPage, reloadToken, requestedPage, sortDirection]);

  useEffect(() => {
    const pendingPhotoId = pendingReturnFocusPhotoIdRef.current;
    if (!pendingPhotoId || isLoading) {
      return;
    }

    const timer = window.setTimeout(() => {
      if (error) {
        headingRef.current?.focus();
        pendingReturnFocusPhotoIdRef.current = null;
        return;
      }

      const focusTarget = document.querySelector<HTMLAnchorElement>(
        `[data-photo-id="${pendingPhotoId}"]`
      );

      if (focusTarget) {
        focusTarget.focus();
      } else {
        headingRef.current?.focus();
      }

      pendingReturnFocusPhotoIdRef.current = null;
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [error, isLoading, photos]);

  const canGoPrevious = requestedPage > 1 && !isLoading;
  const canGoNext = nextCursor !== null && !isLoading;
  const feedbackViewState: FeedbackViewState = isLoading
    ? "loading"
    : error
      ? "error"
      : "ready";

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return `Loading page ${requestedPage}…`;
    }
    if (error) {
      return "Browse results unavailable.";
    }
    return `Showing ${photos.length} of ${totalCount} photos`;
  }, [error, isLoading, photos.length, requestedPage, totalCount]);
  const activeScopeCount = resolveSelectionScopeCount(selectionState, {
    currentPageCount: photos.length,
    totalFilteredCount: totalCount
  });
  const selectionSummaryLabel = `${formatSelectionScopeLabel(selectionState.scope)} scope: ${activeScopeCount} photo${activeScopeCount === 1 ? "" : "s"}`;

  return (
    <section aria-labelledby="page-title" className="page browse-page">
      <div className="browse-header">
        <div>
          <h1 id="page-title" ref={headingRef} tabIndex={-1}>
            Browse
          </h1>
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
      <section className="browse-selection-panel" aria-label="Library selection controls">
        <fieldset className="browse-selection-scope-group">
          <legend>Selection scope</legend>
          <label>
            <input
              type="radio"
              name="browse-selection-scope"
              value="selected"
              checked={selectionState.scope === "selected"}
              onChange={() => {
                dispatchSelection({
                  type: "setScope",
                  scope: "selected",
                  activeFilterFingerprint: BROWSE_FILTER_FINGERPRINT
                });
              }}
            />
            Selected
          </label>
          <label>
            <input
              type="radio"
              name="browse-selection-scope"
              value="page"
              checked={selectionState.scope === "page"}
              onChange={() => {
                dispatchSelection({
                  type: "setScope",
                  scope: "page",
                  activeFilterFingerprint: BROWSE_FILTER_FINGERPRINT
                });
              }}
            />
            This page
          </label>
          <label>
            <input
              type="radio"
              name="browse-selection-scope"
              value="allFiltered"
              checked={selectionState.scope === "allFiltered"}
              onChange={() => {
                dispatchSelection({
                  type: "setScope",
                  scope: "allFiltered",
                  activeFilterFingerprint: BROWSE_FILTER_FINGERPRINT
                });
              }}
            />
            All filtered
          </label>
        </fieldset>
        <p className="browse-selection-summary" aria-live="polite">
          {selectionSummaryLabel}
        </p>
        <button
          type="button"
          onClick={() => {
            dispatchSelection({ type: "clearExplicitSelection" });
          }}
          disabled={selectionState.selectedPhotoIds.size === 0}
        >
          Clear selected
        </button>
      </section>
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

      <FeedbackSurface
        viewState={feedbackViewState}
        loadingLabel="Loading browse workflow."
        error={error ? { title: "Could not load Browse", message: error } : null}
        onRetry={requestRetry}
        notifications={notifications}
        onDismissNotification={(id) => {
          setNotifications((current) => current.filter((entry) => entry.id !== id));
        }}
      >
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
                  <label className="browse-card-selection">
                    <input
                      type="checkbox"
                      checked={selectionState.selectedPhotoIds.has(photo.photo_id)}
                      onChange={() => {
                        dispatchSelection({
                          type: "togglePhotoSelection",
                          photoId: photo.photo_id
                        });
                      }}
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
                          to={`/browse/${photo.photo_id}`}
                          state={{
                            returnToBrowseSearch: location.search,
                            returnFocusPhotoId: photo.photo_id,
                            browseSelection: selectionRouteState
                          }}
                          onClick={() => setPendingBrowseFocusPhotoId(photo.photo_id)}
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
      </FeedbackSurface>
    </section>
  );
}

function areSelectionRouteStatesEqual(
  left: ReturnType<typeof parseLibrarySelectionRouteState>,
  right: ReturnType<typeof serializeLibrarySelectionState>
): boolean {
  if (!left) {
    return false;
  }
  if (left.scope !== right.scope) {
    return false;
  }
  if (left.allFilteredFingerprint !== right.allFilteredFingerprint) {
    return false;
  }
  if (left.selectedPhotoIds.length !== right.selectedPhotoIds.length) {
    return false;
  }

  return left.selectedPhotoIds.every(
    (photoId, index) => photoId === right.selectedPhotoIds[index]
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

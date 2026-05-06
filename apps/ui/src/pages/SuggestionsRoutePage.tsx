import { useEffect, useMemo, useState } from "react";
import ReactPaginate from "react-paginate";

const PAGE_SIZE = 24;

type SuggestionThumbnail = {
  mime_type: string;
  width: number;
  height: number;
  data_base64: string;
};

type TopSuggestion = {
  person_id: string;
  display_name: string;
  confidence: number;
};

type SuggestedFace = {
  face_id: string;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_w?: number | null;
  bbox_h?: number | null;
  top_suggestion: TopSuggestion;
};

type SuggestionPhoto = {
  photo_id: string;
  path: string;
  thumbnail: SuggestionThumbnail | null;
  faces: SuggestedFace[];
};

type SuggestionListPayload = {
  page: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
  };
  items: SuggestionPhoto[];
};

type SuggestionConfirmPayload = {
  assigned: Array<{
    face_id: string;
    photo_id: string;
    person_id: string;
  }>;
  skipped: Array<{
    face_id: string;
    reason: string;
  }>;
};

function formatConfidence(confidence: number): string {
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    return "0.0%";
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

function flattenFaceIds(items: SuggestionPhoto[]): string[] {
  return items.flatMap((photo) => photo.faces.map((face) => face.face_id));
}

async function fetchSuggestionsPage(page: number): Promise<SuggestionListPayload> {
  const response = await fetch(`/api/v1/suggestions/faces?page=${page}&page_size=${PAGE_SIZE}`);
  if (!response.ok) {
    throw new Error(`Suggestions request failed (${response.status})`);
  }
  return (await response.json()) as SuggestionListPayload;
}

async function confirmSuggestions(faceIds: string[]): Promise<SuggestionConfirmPayload> {
  const response = await fetch("/api/v1/suggestions/confirmations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Face-Validation-Role": "contributor"
    },
    body: JSON.stringify({ face_ids: faceIds })
  });
  if (!response.ok) {
    throw new Error(`Confirm request failed (${response.status})`);
  }
  return (await response.json()) as SuggestionConfirmPayload;
}

export function SuggestionsRoutePage() {
  const [page, setPage] = useState(1);
  const [payload, setPayload] = useState<SuggestionListPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFaceIds, setSelectedFaceIds] = useState<Set<string>>(new Set());

  async function load(targetPage: number) {
    setIsLoading(true);
    setError(null);
    try {
      const nextPayload = await fetchSuggestionsPage(targetPage);
      setPayload(nextPayload);
      setSelectedFaceIds(new Set(flattenFaceIds(nextPayload.items)));
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not load suggestions.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load(page);
  }, [page]);

  const selectedFaceIdsOrdered = useMemo(() => {
    const selected = selectedFaceIds;
    if (!payload) {
      return [] as string[];
    }
    return flattenFaceIds(payload.items).filter((faceId) => selected.has(faceId));
  }, [payload, selectedFaceIds]);

  const totalPages = payload?.page.total_pages ?? 0;
  const totalItems = payload?.page.total_items ?? 0;
  const normalizedTotalPages = Number.isInteger(totalPages) && totalPages > 0 ? totalPages : 1;
  const normalizedRequestedPage = Number.isInteger(page) && page > 0 ? page : 1;
  const clampedRequestedPage = Math.min(normalizedRequestedPage, normalizedTotalPages);
  const canGoPrevious = !isLoading && totalPages > 0 && clampedRequestedPage > 1;
  const canGoNext = !isLoading && totalPages > 0 && clampedRequestedPage < totalPages;

  async function handleConfirmFaces() {
    if (isConfirming || selectedFaceIdsOrdered.length === 0) {
      return;
    }

    setIsConfirming(true);
    setMessage(null);
    try {
      const result = await confirmSuggestions(selectedFaceIdsOrdered);
      const assignedCount = result.assigned.length;
      const label = assignedCount === 1 ? "face suggestion" : "face suggestions";
      setMessage(`Confirmed ${assignedCount} ${label}.`);
      await load(page);
    } catch (caughtError: unknown) {
      setMessage(
        caughtError instanceof Error ? caughtError.message : "Could not confirm face suggestions."
      );
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <section className="page suggestions-page" aria-labelledby="suggestions-title">
      <div className="suggestions-header">
        <div>
          <h1 id="suggestions-title">Suggestions</h1>
          <p>Review top face suggestions for unassigned detected faces.</p>
          <p>{`Pending photos: ${totalItems}`}</p>
        </div>
        <div className="suggestions-header-actions">
          <button
            type="button"
            onClick={() => {
              void handleConfirmFaces();
            }}
            disabled={isLoading || isConfirming || selectedFaceIdsOrdered.length === 0}
          >
            Confirm faces
          </button>
        </div>
      </div>

      {isLoading ? <p role="status">Loading suggestions workflow.</p> : null}
      {!isLoading && error ? (
        <div>
          <p>{error}</p>
          <button
            type="button"
            onClick={() => {
              void load(page);
            }}
          >
            Retry
          </button>
        </div>
      ) : null}
      {message ? <p>{message}</p> : null}

      {!isLoading && !error && payload && payload.items.length === 0 ? (
        <p className="suggestions-empty">No pending suggestions.</p>
      ) : null}

      {!isLoading && !error && payload ? (
        <ol className="suggestions-grid" aria-label="Suggestion photo list">
          {payload.items.map((photo) => (
            <li key={photo.photo_id} className="suggestions-card">
              <div className="suggestions-thumbnail-shell">
                {photo.thumbnail ? (
                  <img
                    className="suggestions-thumbnail"
                    src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                    width={photo.thumbnail.width}
                    height={photo.thumbnail.height}
                    alt={`Preview of ${photo.path}`}
                  />
                ) : (
                  <div className="suggestions-thumbnail suggestions-thumbnail-placeholder" aria-hidden="true">
                    No preview
                  </div>
                )}
              </div>
              <div className="suggestions-card-body">
                <p className="suggestions-path" title={photo.path}>
                  {photo.path}
                </p>
                <ul className="suggestions-face-list">
                  {photo.faces.map((face) => {
                    const isSelected = selectedFaceIds.has(face.face_id);
                    return (
                      <li key={face.face_id}>
                        <label>
                          <input
                            type="checkbox"
                            aria-label={`Confirm suggestion for face ${face.face_id}`}
                            checked={isSelected}
                            onChange={() => {
                              setSelectedFaceIds((current) => {
                                const next = new Set(current);
                                if (next.has(face.face_id)) {
                                  next.delete(face.face_id);
                                } else {
                                  next.add(face.face_id);
                                }
                                return next;
                              });
                            }}
                            disabled={isLoading || isConfirming}
                          />
                          <span>{`${face.top_suggestion.display_name} (${formatConfidence(face.top_suggestion.confidence)})`}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </li>
          ))}
        </ol>
      ) : null}

      <nav className="browse-pagination" aria-label="Suggestion pagination">
        <ReactPaginate
          previousLabel="<"
          nextLabel=">"
          breakLabel="..."
          breakAriaLabels={{ backward: "Jump backward", forward: "Jump forward" }}
          pageCount={normalizedTotalPages}
          pageRangeDisplayed={3}
          marginPagesDisplayed={1}
          forcePage={clampedRequestedPage - 1}
          disableInitialCallback
          renderOnZeroPageCount={null}
          onClick={(clickEvent) => {
            if (!canGoPrevious && !canGoNext) {
              return false;
            }
            if (clickEvent.isPrevious && !canGoPrevious) {
              return false;
            }
            if (clickEvent.isNext && !canGoNext) {
              return false;
            }
            return undefined;
          }}
          onPageChange={({ selected }) => setPage(selected + 1)}
          pageLabelBuilder={(value) => `[${value}]`}
          ariaLabelBuilder={(value) => `Page ${value}`}
          containerClassName="browse-pagination-pages"
          pageClassName="browse-pagination-page-item"
          pageLinkClassName="browse-pagination-page-link"
          previousClassName="browse-pagination-page-item"
          nextClassName="browse-pagination-page-item"
          previousLinkClassName="browse-pagination-page-link browse-pagination-arrow"
          nextLinkClassName="browse-pagination-page-link browse-pagination-arrow"
          activeClassName="is-active"
          disabledClassName="is-disabled"
          breakClassName="browse-pagination-break-item"
          breakLinkClassName="browse-pagination-ellipsis"
        />
      </nav>
    </section>
  );
}

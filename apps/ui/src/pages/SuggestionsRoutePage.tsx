import { useEffect, useMemo, useRef, useState } from "react";
import ReactPaginate from "react-paginate";
import { Link } from "react-router-dom";
import { FaceBBoxOverlay, buildFaceOverlayRegions } from "./FaceBBoxOverlay";
import {
  loadSuggestionsFilterState,
  saveSuggestionsFilterState
} from "./suggestions/suggestionsRouteMemory";

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
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
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

type PersonRecord = {
  person_id: string;
  display_name: string;
};

function formatConfidence(confidence: number): string {
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    return "0.0%";
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

function formatDisplayPath(path: string): string {
  const marker = "/storage-sources/";
  const markerIndex = path.indexOf(marker);
  if (markerIndex < 0) {
    return path;
  }

  const pathAfterMarker = path.slice(markerIndex + marker.length);
  const firstSlashAfterSourceId = pathAfterMarker.indexOf("/");
  if (firstSlashAfterSourceId < 0) {
    return path;
  }

  const sourceRelativePath = pathAfterMarker.slice(firstSlashAfterSourceId + 1).trim();
  if (!sourceRelativePath) {
    return path;
  }

  return `.../${sourceRelativePath}`;
}

function flattenFaceIds(items: SuggestionPhoto[]): string[] {
  return items.flatMap((photo) => photo.faces.map((face) => face.face_id));
}

async function fetchSuggestionsPage(
  page: number,
  minConfidenceThreshold: number
): Promise<SuggestionListPayload> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(PAGE_SIZE)
  });
  if (minConfidenceThreshold > 0) {
    params.set("min_confidence", String(minConfidenceThreshold));
  }
  const response = await fetch(`/api/v1/suggestions/faces?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Suggestions request failed (${response.status})`);
  }
  return (await response.json()) as SuggestionListPayload;
}

async function fetchPeopleDirectory(): Promise<PersonRecord[]> {
  const response = await fetch("/api/v1/people");
  if (!response.ok) {
    throw new Error(`People request failed (${response.status})`);
  }
  return (await response.json()) as PersonRecord[];
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
  const initialStoredFiltersRef = useRef(loadSuggestionsFilterState());
  const [page, setPage] = useState(1);
  const [minConfidencePercent, setMinConfidencePercent] = useState(
    initialStoredFiltersRef.current?.minConfidencePercent ?? 0
  );
  const [excludedPersonIds, setExcludedPersonIds] = useState<string[]>(
    initialStoredFiltersRef.current?.excludedPersonIds ?? []
  );
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const [payload, setPayload] = useState<SuggestionListPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFaceIds, setSelectedFaceIds] = useState<Set<string>>(new Set());

  const minConfidenceThreshold = minConfidencePercent / 100;
  const excludedPersonIdSet = useMemo(() => new Set(excludedPersonIds), [excludedPersonIds]);

  async function load(targetPage: number) {
    setIsLoading(true);
    setError(null);
    try {
      const nextPayload = await fetchSuggestionsPage(targetPage, minConfidenceThreshold);
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
  }, [page, minConfidenceThreshold]);

  useEffect(() => {
    let isCanceled = false;

    async function loadPeople() {
      try {
        const people = await fetchPeopleDirectory();
        if (!isCanceled) {
          setPeopleDirectory(people);
        }
      } catch {
        if (!isCanceled) {
          setPeopleDirectory([]);
        }
      }
    }

    void loadPeople();

    return () => {
      isCanceled = true;
    };
  }, []);

  useEffect(() => {
    saveSuggestionsFilterState({
      minConfidencePercent,
      excludedPersonIds
    });
  }, [excludedPersonIds, minConfidencePercent]);

  const visibleItems = useMemo(() => {
    if (!payload) {
      return [] as SuggestionPhoto[];
    }
    return payload.items
      .map((photo) => ({
        ...photo,
        faces: photo.faces.filter((face) => !excludedPersonIdSet.has(face.top_suggestion.person_id))
      }))
      .filter((photo) => photo.faces.length > 0);
  }, [excludedPersonIdSet, payload]);

  const currentPageFaceIdsOrdered = useMemo(() => {
    return flattenFaceIds(visibleItems);
  }, [visibleItems]);

  const selectedFaceIdsOrdered = useMemo(() => {
    const selected = selectedFaceIds;
    return currentPageFaceIdsOrdered.filter((faceId) => selected.has(faceId));
  }, [currentPageFaceIdsOrdered, selectedFaceIds]);

  const excludedPeople = useMemo(
    () => peopleDirectory.filter((person) => excludedPersonIdSet.has(person.person_id)),
    [excludedPersonIdSet, peopleDirectory]
  );

  const totalPages = payload?.page.total_pages ?? 0;
  const totalItems = visibleItems.length;
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
      const checkedFaceIdsOnCurrentPage = currentPageFaceIdsOrdered.filter((faceId) =>
        selectedFaceIds.has(faceId)
      );
      const result = await confirmSuggestions(checkedFaceIdsOnCurrentPage);
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

  function toggleExcludedPerson(personId: string) {
    setExcludedPersonIds((current) => {
      if (current.includes(personId)) {
        return current.filter((entry) => entry !== personId);
      }
      return [...current, personId];
    });
    setPage(1);
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
          <div className="suggestions-filter-group">
            <label className="suggestions-confidence-filter">
              <span>{`Minimum certainty: ${minConfidencePercent}%`}</span>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={minConfidencePercent}
                aria-label="Minimum suggestion certainty"
                onChange={(event) => {
                  setMinConfidencePercent(Number(event.currentTarget.value));
                  setPage(1);
                }}
                disabled={isLoading || isConfirming}
              />
            </label>
            {peopleDirectory.length > 0 ? (
              <div className="suggestions-people-filter">
                <p className="suggestions-filter-label">Exclude people</p>
                <ul className="search-chip-list suggestions-active-filters" aria-label="Excluded people filters">
                  {peopleDirectory.map((person) => {
                    const excluded = excludedPersonIdSet.has(person.person_id);
                    return (
                      <li key={person.person_id}>
                        <button
                          type="button"
                          className={excluded ? "search-chip search-chip-active" : "search-chip"}
                          aria-pressed={excluded}
                          aria-label={`Exclude ${person.display_name}`}
                          onClick={() => toggleExcludedPerson(person.person_id)}
                          disabled={isLoading || isConfirming}
                        >
                          {person.display_name}
                        </button>
                      </li>
                    );
                  })}
                </ul>
                {excludedPeople.length > 0 ? (
                  <ul className="search-chip-list suggestions-active-filters" aria-label="Active excluded people">
                    {excludedPeople.map((person) => (
                      <li key={person.person_id}>
                        <button
                          type="button"
                          className="search-chip search-chip-active"
                          aria-label={`Remove excluded person ${person.display_name}`}
                          onClick={() => toggleExcludedPerson(person.person_id)}
                          disabled={isLoading || isConfirming}
                        >
                          {`excluded: ${person.display_name}`}
                          <span aria-hidden="true"> ×</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
          <button
            type="button"
            className="suggestions-confirm-button"
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

      {!isLoading && !error && payload && visibleItems.length === 0 ? (
        <p className="suggestions-empty">No pending suggestions.</p>
      ) : null}

      {!isLoading && !error && payload ? (
        <ol className="suggestions-grid" aria-label="Suggestion photo list">
          {visibleItems.map((photo) => {
            const numberedFaces = photo.faces.map((face, index) => ({
              ...face,
              faceNumber: index + 1
            }));
            const faceNumberById = new Map(
              numberedFaces.map((face) => [face.face_id, face.faceNumber] as const)
            );
            const overlayRegions =
              photo.thumbnail
                ? buildFaceOverlayRegions(
                    numberedFaces.map((face) => ({
                      face_id: face.face_id,
                      person_id: null,
                      bbox_x: face.bbox_x ?? null,
                      bbox_y: face.bbox_y ?? null,
                      bbox_w: face.bbox_w ?? null,
                      bbox_h: face.bbox_h ?? null,
                      bbox_space_width: face.bbox_space_width ?? null,
                      bbox_space_height: face.bbox_space_height ?? null
                    })),
                    photo.thumbnail.width,
                    photo.thumbnail.height
                  )
                : [];
            const thumbnailShellStyle = photo.thumbnail
              ? { aspectRatio: `${photo.thumbnail.width} / ${photo.thumbnail.height}` }
              : undefined;
            return (
              <li key={photo.photo_id} className="suggestions-card">
                <div className="suggestions-thumbnail-shell" style={thumbnailShellStyle}>
                  <Link
                    className="suggestions-thumbnail-link"
                    to={`/library/${photo.photo_id}`}
                    aria-label={`Open details for ${photo.path}`}
                  >
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
                    <FaceBBoxOverlay
                      regions={overlayRegions}
                      ariaLabel={`Suggested face regions for ${photo.path}`}
                      renderRegionContent={(region) => (
                        <span className="suggestions-face-overlay-badge" aria-hidden="true">
                          {faceNumberById.get(region.faceId) ?? "?"}
                        </span>
                      )}
                    />
                  </Link>
                </div>
                <div className="suggestions-card-body">
                  <p className="suggestions-path" title={photo.path}>
                    {formatDisplayPath(photo.path)}
                  </p>
                  <ul className="suggestions-face-list">
                    {photo.faces.map((face, index) => {
                      const isSelected = selectedFaceIds.has(face.face_id);
                      const faceNumber = index + 1;
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
                            <span>{`Face ${faceNumber}: ${face.top_suggestion.display_name} (${formatConfidence(face.top_suggestion.confidence)})`}</span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              </li>
            );
          })}
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

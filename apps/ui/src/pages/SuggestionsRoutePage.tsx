import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactPaginate from "react-paginate";

import { SuggestionsFilters } from "./suggestions/SuggestionsFilters";
import { SuggestionsGrid } from "./suggestions/SuggestionsGrid";
import { fetchPeopleDirectory, fetchSuggestionsPage } from "./suggestions/api";
import { loadSuggestionsFilterState, saveSuggestionsFilterState } from "./suggestions/suggestionsRouteMemory";
import type { PersonRecord, SuggestionPhoto, SuggestionListPayload } from "./suggestions/types";
import { useSuggestionsActions } from "./suggestions/useSuggestionsActions";

const PAGE_SIZE = 24;

function flattenFaceIds(items: SuggestionPhoto[]): string[] {
  return items.flatMap((photo) => photo.faces.map((face) => face.face_id));
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
  const [error, setError] = useState<string | null>(null);
  const [selectedFaceIds, setSelectedFaceIds] = useState<Set<string>>(new Set());
  const [faceChoiceDrafts, setFaceChoiceDrafts] = useState<Map<string, string>>(new Map());
  const [excludedPersonPickerValue, setExcludedPersonPickerValue] = useState("");

  const minConfidenceThreshold = minConfidencePercent / 100;
  const excludedPersonIdSet = useMemo(() => new Set(excludedPersonIds), [excludedPersonIds]);

  const loadPage = useCallback(
    async (targetPage: number) => {
      setIsLoading(true);
      setError(null);
      try {
        const nextPayload = await fetchSuggestionsPage(
          targetPage,
          PAGE_SIZE,
          minConfidenceThreshold,
          excludedPersonIds
        );
        setPayload(nextPayload);
        setSelectedFaceIds(new Set(flattenFaceIds(nextPayload.items)));
        const nextDrafts = new Map<string, string>();
        for (const photo of nextPayload.items) {
          for (const face of photo.faces) {
            nextDrafts.set(face.face_id, face.top_suggestion.display_name);
          }
        }
        setFaceChoiceDrafts(nextDrafts);
      } catch (caughtError: unknown) {
        setError(caughtError instanceof Error ? caughtError.message : "Could not load suggestions.");
      } finally {
        setIsLoading(false);
      }
    },
    [excludedPersonIds, minConfidenceThreshold]
  );

  useEffect(() => {
    void loadPage(page);
  }, [loadPage, page]);

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
      excludedPersonIds,
    });
  }, [excludedPersonIds, minConfidencePercent]);

  const currentPageFaceIdsOrdered = useMemo(() => flattenFaceIds(payload?.items ?? []), [payload]);

  const selectedFaceIdsOrdered = useMemo(() => {
    const selected = selectedFaceIds;
    return currentPageFaceIdsOrdered.filter((faceId) => selected.has(faceId));
  }, [currentPageFaceIdsOrdered, selectedFaceIds]);

  const excludedPeople = useMemo(
    () => peopleDirectory.filter((person) => excludedPersonIdSet.has(person.person_id)),
    [excludedPersonIdSet, peopleDirectory]
  );

  const availablePeopleToExclude = useMemo(
    () => peopleDirectory.filter((person) => !excludedPersonIdSet.has(person.person_id)),
    [excludedPersonIdSet, peopleDirectory]
  );

  const totalPages = payload?.page.total_pages ?? 0;
  const totalItems = payload?.page.total_items ?? 0;
  const normalizedTotalPages = Number.isInteger(totalPages) && totalPages > 0 ? totalPages : 1;
  const normalizedRequestedPage = Number.isInteger(page) && page > 0 ? page : 1;
  const clampedRequestedPage = Math.min(normalizedRequestedPage, normalizedTotalPages);
  const canGoPrevious = !isLoading && totalPages > 0 && clampedRequestedPage > 1;
  const canGoNext = !isLoading && totalPages > 0 && clampedRequestedPage < totalPages;

  const {
    isConfirming,
    message,
    faceActionInFlightIds,
    handleConfirmFaces,
    handleConfirmSingleFace,
    handleMarkFaceUnknown,
    handleDismissFalsePositive,
  } = useSuggestionsActions({
    isLoading,
    page,
    payloadItems: payload?.items ?? [],
    peopleDirectory,
    currentPageFaceIdsOrdered,
    selectedFaceIds,
    faceChoiceDrafts,
    loadPage,
    setPeopleDirectory,
  });

  function addExcludedPerson(personId: string) {
    setExcludedPersonIds((current) => {
      if (current.includes(personId)) {
        return current;
      }
      return [...current, personId];
    });
    setPage(1);
  }

  function removeExcludedPerson(personId: string) {
    setExcludedPersonIds((current) => current.filter((entry) => entry !== personId));
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
          <SuggestionsFilters
            minConfidencePercent={minConfidencePercent}
            isLoading={isLoading}
            isConfirming={isConfirming}
            peopleDirectory={peopleDirectory}
            availablePeopleToExclude={availablePeopleToExclude}
            excludedPeople={excludedPeople}
            excludedPersonPickerValue={excludedPersonPickerValue}
            onMinConfidenceChange={(value) => {
              setMinConfidencePercent(value);
              setPage(1);
            }}
            onExcludedPersonPickerValueChange={setExcludedPersonPickerValue}
            onAddExcludedPerson={addExcludedPerson}
            onRemoveExcludedPerson={removeExcludedPerson}
          />
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
              void loadPage(page);
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
        <SuggestionsGrid
          items={payload.items}
          selectedFaceIds={selectedFaceIds}
          faceActionInFlightIds={faceActionInFlightIds}
          faceChoiceDrafts={faceChoiceDrafts}
          isLoading={isLoading}
          isConfirming={isConfirming}
          onToggleFaceSelected={(faceId) => {
            setSelectedFaceIds((current) => {
              const next = new Set(current);
              if (next.has(faceId)) {
                next.delete(faceId);
              } else {
                next.add(faceId);
              }
              return next;
            });
          }}
          onFaceChoiceChange={(faceId, value) => {
            setFaceChoiceDrafts((current) => {
              const next = new Map(current);
              next.set(faceId, value);
              return next;
            });
          }}
          onConfirmSingleFace={(face) => {
            void handleConfirmSingleFace(face);
          }}
          onMarkFaceUnknown={(face) => {
            void handleMarkFaceUnknown(face);
          }}
          onDismissFalsePositive={(face) => {
            void handleDismissFalsePositive(face);
          }}
        />
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

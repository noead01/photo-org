import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseAsArrayOf, parseAsInteger, parseAsString, useQueryState } from "nuqs";
import { BrowsePagination } from "./shared/BrowsePagination";

import { SuggestionsFilters } from "./suggestions/SuggestionsFilters";
import { SuggestionsGrid } from "./suggestions/SuggestionsGrid";
import { fetchPeopleDirectory, fetchSuggestionsPage } from "./suggestions/api";
import type { PersonRecord, SuggestionPhoto, SuggestionListPayload } from "./suggestions/types";
import { useSuggestionsActions } from "./suggestions/useSuggestionsActions";

const PAGE_SIZE = 24;

function flattenFaceIds(items: SuggestionPhoto[]): string[] {
  return items.flatMap((photo) => photo.faces.map((face) => face.face_id));
}

export function SuggestionsRoutePage() {
  const [minConfidenceQueryValue, setMinConfidenceQueryValue] = useQueryState(
    "minConfidence",
    parseAsInteger.withDefault(0).withOptions({ history: "replace" })
  );
  const [maxConfidenceQueryValue, setMaxConfidenceQueryValue] = useQueryState(
    "maxConfidence",
    parseAsInteger.withDefault(100).withOptions({ history: "replace" })
  );
  const [excludedPersonIdsQueryValue, setExcludedPersonIdsQueryValue] = useQueryState(
    "excludedPersonId",
    parseAsArrayOf(parseAsString).withDefault([]).withOptions({ history: "replace" })
  );
  const [page, setPage] = useState(1);
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const [payload, setPayload] = useState<SuggestionListPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedFaceIds, setSelectedFaceIds] = useState<Set<string>>(new Set());
  const [faceChoiceDrafts, setFaceChoiceDrafts] = useState<Map<string, string>>(new Map());
  const [excludedPersonPickerValue, setExcludedPersonPickerValue] = useState("");

  const minConfidencePercent = clampPercentage(minConfidenceQueryValue);
  const maxConfidencePercent = Math.max(
    minConfidencePercent,
    clampPercentage(maxConfidenceQueryValue)
  );
  const excludedPersonIdsKey = excludedPersonIdsQueryValue
    .map((personId) => personId.trim())
    .filter((personId) => personId.length > 0)
    .join("\u001f");
  const excludedPersonIds = useMemo(
    () => (excludedPersonIdsKey.length > 0 ? excludedPersonIdsKey.split("\u001f") : []),
    [excludedPersonIdsKey]
  );
  const minConfidenceThreshold = minConfidencePercent / 100;
  const maxConfidenceThreshold = maxConfidencePercent / 100;
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
          maxConfidenceThreshold,
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
    [excludedPersonIds, maxConfidenceThreshold, minConfidenceThreshold]
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
  const canGoPrevious = !isLoading && totalPages > 0 && page > 1;
  const canGoNext = !isLoading && totalPages > 0 && page < totalPages;

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
    const nextExcludedIds = excludedPersonIds.includes(personId)
      ? excludedPersonIds
      : [...excludedPersonIds, personId];
    void setExcludedPersonIdsQueryValue(nextExcludedIds);
    setPage(1);
  }

  function removeExcludedPerson(personId: string) {
    void setExcludedPersonIdsQueryValue(excludedPersonIds.filter((entry) => entry !== personId));
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
            maxConfidencePercent={maxConfidencePercent}
            isLoading={isLoading}
            isConfirming={isConfirming}
            peopleDirectory={peopleDirectory}
            availablePeopleToExclude={availablePeopleToExclude}
            excludedPeople={excludedPeople}
            excludedPersonPickerValue={excludedPersonPickerValue}
            onConfidenceRangeChange={(minValue, maxValue) => {
              void setMinConfidenceQueryValue(minValue);
              void setMaxConfidenceQueryValue(maxValue);
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

      <BrowsePagination
        currentPage={page}
        pageCount={totalPages}
        canGoPrevious={canGoPrevious}
        canGoNext={canGoNext}
        ariaLabel="Suggestion pagination"
        onPageChange={setPage}
      />
    </section>
  );
}

function clampPercentage(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

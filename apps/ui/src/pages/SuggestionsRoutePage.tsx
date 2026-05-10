import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { parseAsArrayOf, parseAsInteger, parseAsString, useQueryState } from "nuqs";
import { resolveInitialSessionIdentity } from "../session/sessionIdentity";
import {
  addPhotosToAlbum,
  createAlbum,
  fetchAlbums
} from "./library/libraryRouteApi";
import { AlbumActionSurface } from "./photo-interactions/AlbumActionSurface";
import { FaceAssignmentModal } from "./photo-interactions/FaceAssignmentModal";
import { PhotoMetadataFlyout } from "./photo-interactions/PhotoMetadataFlyout";
import { adaptSuggestionPhoto } from "./photo-interactions/photoInteractionAdapters";
import {
  DEFAULT_PHOTO_INSPECTOR_STATE,
  photoInspectorReducer
} from "./photo-interactions/photoInspectorState";
import {
  DEFAULT_PHOTO_SELECTION_STATE,
  photoSelectionReducer
} from "./photo-interactions/photoSelectionState";
import type { AlbumTarget } from "./photo-interactions/photoInteractionTypes";
import { fetchPhotoDetail } from "./photo-detail/photoDetailApi";
import type { PhotoDetailPayload } from "./photo-detail/photoDetailTypes";
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
  const [selectionState, dispatchSelection] = useReducer(
    photoSelectionReducer,
    DEFAULT_PHOTO_SELECTION_STATE
  );
  const [photoInspectorState, dispatchPhotoInspector] = useReducer(
    photoInspectorReducer,
    {
      ...DEFAULT_PHOTO_INSPECTOR_STATE,
      areFaceBoxesVisible: true
    }
  );
  const [selectedFaceIds, setSelectedFaceIds] = useState<Set<string>>(new Set());
  const [faceChoiceDrafts, setFaceChoiceDrafts] = useState<Map<string, string>>(new Map());
  const [excludedPersonPickerValue, setExcludedPersonPickerValue] = useState("");
  const [albumTargets, setAlbumTargets] = useState<AlbumTarget[]>([]);
  const [isAlbumActionSubmitting, setIsAlbumActionSubmitting] = useState(false);
  const [albumActionResultMessage, setAlbumActionResultMessage] = useState<string | null>(null);
  const [isFaceInteractionEnabled, setIsFaceInteractionEnabled] = useState(true);
  const [isAlbumInteractionEnabled, setIsAlbumInteractionEnabled] = useState(true);
  const [photoDetailById, setPhotoDetailById] = useState<Record<string, PhotoDetailPayload>>({});
  const [photoDetailErrorById, setPhotoDetailErrorById] = useState<Record<string, string>>({});
  const [loadingPhotoDetailId, setLoadingPhotoDetailId] = useState<string | null>(null);
  const sessionIdentity = resolveInitialSessionIdentity();
  const sessionUserId = sessionIdentity?.userId ?? null;

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
    let canceled = false;

    async function loadReferenceData() {
      try {
        const people = await fetchPeopleDirectory();
        if (!canceled) {
          setPeopleDirectory(people);
        }
      } catch {
        if (!canceled) {
          setPeopleDirectory([]);
        }
      }

      try {
        const albums = await fetchAlbums(sessionUserId);
        if (!canceled) {
          const mappedTargets = albums
            .map<AlbumTarget>((album) => ({
              albumId: album.album_id,
              name: album.name,
              kind: album.kind === "saved_filter" ? "saved_filter" : "manual",
              canAcceptManualAdditions: album.kind === "editable"
            }))
            .sort((left, right) => left.name.localeCompare(right.name, "en-US"));
          setAlbumTargets(mappedTargets);
        }
      } catch {
        if (!canceled) {
          setAlbumTargets([]);
        }
      }
    }

    void loadReferenceData();

    return () => {
      canceled = true;
    };
  }, [sessionUserId]);

  useEffect(() => {
    if (isFaceInteractionEnabled) {
      return;
    }
    dispatchPhotoInspector({ type: "closeFaceAssignment" });
  }, [isFaceInteractionEnabled]);

  const activeInspectorPhotoId =
    photoInspectorState.activeMetadataPhotoId ?? photoInspectorState.activeFaceAssignment?.photoId ?? null;

  useEffect(() => {
    if (!activeInspectorPhotoId || photoDetailById[activeInspectorPhotoId]) {
      return;
    }
    let canceled = false;
    setLoadingPhotoDetailId(activeInspectorPhotoId);
    setPhotoDetailErrorById((current) => {
      if (!current[activeInspectorPhotoId]) {
        return current;
      }
      const next = { ...current };
      delete next[activeInspectorPhotoId];
      return next;
    });

    void fetchPhotoDetail(activeInspectorPhotoId)
      .then((detailPayload) => {
        if (!canceled) {
          setPhotoDetailById((current) => ({
            ...current,
            [activeInspectorPhotoId]: detailPayload
          }));
        }
      })
      .catch((caughtError: unknown) => {
        if (!canceled) {
          setPhotoDetailErrorById((current) => ({
            ...current,
            [activeInspectorPhotoId]:
              caughtError instanceof Error ? caughtError.message : "Could not load photo detail."
          }));
        }
      })
      .finally(() => {
        if (!canceled) {
          setLoadingPhotoDetailId((current) => (
            current === activeInspectorPhotoId ? null : current
          ));
        }
      });

    return () => {
      canceled = true;
    };
  }, [activeInspectorPhotoId, photoDetailById]);

  const currentPageFaceIdsOrdered = useMemo(() => flattenFaceIds(payload?.items ?? []), [payload]);
  const currentPagePhotoIdsOrdered = useMemo(
    () => (payload?.items ?? []).map((item) => item.photo_id),
    [payload]
  );
  const selectedPhotoIdsOrdered = useMemo(() => {
    const selectedPhotoIds = selectionState.selectedPhotoIds;
    return currentPagePhotoIdsOrdered.filter((photoId) => selectedPhotoIds.has(photoId));
  }, [currentPagePhotoIdsOrdered, selectionState.selectedPhotoIds]);

  const selectedFaceIdsOrdered = useMemo(() => {
    const selected = selectedFaceIds;
    return currentPageFaceIdsOrdered.filter((faceId) => selected.has(faceId));
  }, [currentPageFaceIdsOrdered, selectedFaceIds]);

  const summaryByPhotoId = useMemo(() => {
    const summaries = new Map<string, ReturnType<typeof adaptSuggestionPhoto>>();
    for (const item of payload?.items ?? []) {
      summaries.set(item.photo_id, adaptSuggestionPhoto(item));
    }
    return summaries;
  }, [payload?.items]);

  const activeMetadataSummary = useMemo(() => {
    const photoId = photoInspectorState.activeMetadataPhotoId;
    if (!photoId) {
      return null;
    }
    const summary = summaryByPhotoId.get(photoId);
    if (summary) {
      return {
        photoId: summary.photoId,
        title: summary.title,
        path: summary.path,
        thumbnail: summary.media.thumbnail
      };
    }
    return {
      photoId,
      title: photoId,
      path: photoId,
      thumbnail: null
    };
  }, [photoInspectorState.activeMetadataPhotoId, summaryByPhotoId]);

  const activeMetadataDetail = photoInspectorState.activeMetadataPhotoId
    ? photoDetailById[photoInspectorState.activeMetadataPhotoId] ?? null
    : null;
  const activeMetadataError = photoInspectorState.activeMetadataPhotoId
    ? photoDetailErrorById[photoInspectorState.activeMetadataPhotoId] ?? null
    : null;
  const isLoadingMetadataDetail =
    photoInspectorState.activeMetadataPhotoId !== null
    && loadingPhotoDetailId === photoInspectorState.activeMetadataPhotoId;

  const activeFaceSummary = useMemo(() => {
    const activeFaceAssignment = photoInspectorState.activeFaceAssignment;
    if (!activeFaceAssignment || !isFaceInteractionEnabled) {
      return null;
    }
    return summaryByPhotoId.get(activeFaceAssignment.photoId) ?? null;
  }, [photoInspectorState.activeFaceAssignment, isFaceInteractionEnabled, summaryByPhotoId]);

  const activeFace = useMemo(() => {
    const activeFaceAssignment = photoInspectorState.activeFaceAssignment;
    if (!activeFaceAssignment || !activeFaceSummary) {
      return null;
    }
    return activeFaceSummary.faces.find((face) => face.faceId === activeFaceAssignment.faceId) ?? null;
  }, [activeFaceSummary, photoInspectorState.activeFaceAssignment]);

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

  async function handleAddToAlbum(albumId: string, photoIds: string[]) {
    if (isAlbumActionSubmitting) {
      return;
    }

    setIsAlbumActionSubmitting(true);
    setAlbumActionResultMessage(null);
    try {
      const result = await addPhotosToAlbum(albumId, photoIds, sessionUserId);
      const addedCount = result.added_photo_ids.length;
      const duplicateCount = result.duplicate_photo_ids.length;
      const missingCount = result.missing_photo_ids.length;
      const details: string[] = [];
      if (duplicateCount > 0) {
        details.push(`${duplicateCount} already in album`);
      }
      if (missingCount > 0) {
        details.push(`${missingCount} missing`);
      }
      const summary = `Added ${addedCount} photo${addedCount === 1 ? "" : "s"} to album.`;
      setAlbumActionResultMessage(
        details.length > 0 ? `${summary} (${details.join(", ")}).` : summary
      );
    } catch (caughtError: unknown) {
      setAlbumActionResultMessage(
        caughtError instanceof Error ? caughtError.message : "Could not add photos to album."
      );
    } finally {
      setIsAlbumActionSubmitting(false);
    }
  }

  async function handleCreateAlbumAndAdd(name: string, photoIds: string[]) {
    if (isAlbumActionSubmitting) {
      return;
    }

    setIsAlbumActionSubmitting(true);
    setAlbumActionResultMessage(null);
    try {
      const createdAlbum = await createAlbum({ name, kind: "editable" }, sessionUserId);
      await addPhotosToAlbum(createdAlbum.album_id, photoIds, sessionUserId);
      setAlbumTargets((current) =>
        [...current, {
          albumId: createdAlbum.album_id,
          name: createdAlbum.name,
          kind: "manual" as const,
          canAcceptManualAdditions: true
        }].sort((left, right) => left.name.localeCompare(right.name, "en-US"))
      );
      setAlbumActionResultMessage(
        `Created album "${createdAlbum.name}" and added ${photoIds.length} photo${photoIds.length === 1 ? "" : "s"}.`
      );
    } catch (caughtError: unknown) {
      setAlbumActionResultMessage(
        caughtError instanceof Error ? caughtError.message : "Could not create album."
      );
    } finally {
      setIsAlbumActionSubmitting(false);
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
            disabled={
              isLoading
              || isConfirming
              || !isFaceInteractionEnabled
              || selectedFaceIdsOrdered.length === 0
            }
          >
            Confirm faces
          </button>
        </div>
      </div>

      <section className="suggestions-interaction-toggles" aria-label="Interaction toggles">
        <label className="suggestions-toggle">
          <input
            type="checkbox"
            checked={isFaceInteractionEnabled}
            onChange={(event) => {
              setIsFaceInteractionEnabled(event.currentTarget.checked);
            }}
            aria-label="Enable face assignment interactions"
          />
          Enable face assignment interactions
        </label>
        <label className="suggestions-toggle">
          <input
            type="checkbox"
            checked={photoInspectorState.areFaceBoxesVisible}
            disabled={!isFaceInteractionEnabled}
            onChange={(event) => {
              dispatchPhotoInspector({
                type: "setFaceBoxesVisible",
                visible: event.currentTarget.checked
              });
            }}
            aria-label="Show face boxes on all photos"
          />
          Show face boxes on all photos
        </label>
        <label className="suggestions-toggle">
          <input
            type="checkbox"
            checked={isAlbumInteractionEnabled}
            onChange={(event) => {
              setIsAlbumInteractionEnabled(event.currentTarget.checked);
            }}
            aria-label="Enable album interactions"
          />
          Enable album interactions
        </label>
      </section>

      {isLoading ? <p className="suggestions-status" role="status">Loading suggestions workflow.</p> : null}
      {!isLoading && error ? (
        <div className="suggestions-error">
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
      {message ? <p className="suggestions-message">{message}</p> : null}

      {isAlbumInteractionEnabled ? (
        <AlbumActionSurface
          albums={albumTargets}
          selectedPhotoIds={selectedPhotoIdsOrdered}
          isSubmitting={isAlbumActionSubmitting}
          resultMessage={albumActionResultMessage}
          onAddToAlbum={(albumId, photoIds) => {
            void handleAddToAlbum(albumId, photoIds);
          }}
          onCreateAlbumAndAdd={(name, photoIds) => {
            void handleCreateAlbumAndAdd(name, photoIds);
          }}
        />
      ) : null}

      {!isLoading && !error && payload && payload.items.length === 0 ? (
        <p className="suggestions-empty">No pending suggestions.</p>
      ) : null}

      {!isLoading && !error && payload ? (
        <SuggestionsGrid
          items={payload.items}
          selectedPhotoIds={selectionState.selectedPhotoIds}
          selectedFaceIds={selectedFaceIds}
          faceBoxesVisible={isFaceInteractionEnabled && photoInspectorState.areFaceBoxesVisible}
          isFaceInteractionEnabled={isFaceInteractionEnabled}
          activeMetadataPhotoId={photoInspectorState.activeMetadataPhotoId}
          faceActionInFlightIds={faceActionInFlightIds}
          faceChoiceDrafts={faceChoiceDrafts}
          isLoading={isLoading}
          isConfirming={isConfirming}
          onTogglePhotoSelected={(photoId) => {
            dispatchSelection({
              type: "togglePhotoSelection",
              photoId
            });
          }}
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
          onOpenMetadata={(photoId, sourceSurfaceId) => {
            dispatchPhotoInspector({
              type: "openMetadata",
              photoId,
              sourceSurfaceId
            });
          }}
          onOpenFace={(face, photoId, sourceSurfaceId) => {
            if (!isFaceInteractionEnabled) {
              return;
            }
            dispatchPhotoInspector({
              type: "openFaceAssignment",
              photoId,
              faceId: face.face_id,
              sourceSurfaceId
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
            if (!isFaceInteractionEnabled) {
              return;
            }
            void handleConfirmSingleFace(face);
          }}
          onMarkFaceUnknown={(face) => {
            if (!isFaceInteractionEnabled) {
              return;
            }
            void handleMarkFaceUnknown(face);
          }}
          onDismissFalsePositive={(face) => {
            if (!isFaceInteractionEnabled) {
              return;
            }
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

      <PhotoMetadataFlyout
        isOpen={photoInspectorState.activeMetadataPhotoId !== null}
        summary={activeMetadataSummary}
        detail={activeMetadataDetail}
        isLoadingDetail={isLoadingMetadataDetail}
        detailError={activeMetadataError}
        onClose={() => dispatchPhotoInspector({ type: "closeMetadata" })}
        onRetry={() => {
          const photoId = photoInspectorState.activeMetadataPhotoId;
          if (!photoId) {
            return;
          }
          setPhotoDetailById((current) => {
            const next = { ...current };
            delete next[photoId];
            return next;
          });
        }}
      />

      <FaceAssignmentModal
        isOpen={activeFace !== null}
        photo={activeFaceSummary}
        face={activeFace}
        people={peopleDirectory.map((person) => ({
          person_id: person.person_id,
          display_name: person.display_name
        }))}
        onClose={() => dispatchPhotoInspector({ type: "closeFaceAssignment" })}
        onFaceUpdated={() => {
          dispatchPhotoInspector({ type: "closeFaceAssignment" });
          void loadPage(page);
        }}
        onFaceDismissed={() => {
          dispatchPhotoInspector({ type: "closeFaceAssignment" });
          void loadPage(page);
        }}
        onPersonCreated={(person) => {
          setPeopleDirectory((current) => {
            if (current.some((candidate) => candidate.person_id === person.person_id)) {
              return current;
            }
            return [
              ...current,
              {
                person_id: person.person_id,
                display_name: person.display_name
              }
            ];
          });
        }}
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

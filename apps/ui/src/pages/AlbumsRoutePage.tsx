import { useEffect, useMemo, useReducer, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchPhotoDetail, fetchPeopleDirectory } from "./photo-detail/photoDetailApi";
import type { PhotoDetailPayload, PersonRecord } from "./photo-detail/photoDetailTypes";
import { FaceAssignmentModal } from "./photo-interactions/FaceAssignmentModal";
import { PhotoMetadataFlyout } from "./photo-interactions/PhotoMetadataFlyout";
import {
  DEFAULT_PHOTO_INSPECTOR_STATE,
  photoInspectorReducer
} from "./photo-interactions/photoInspectorState";
import {
  DEFAULT_PHOTO_SELECTION_STATE,
  photoSelectionReducer
} from "./photo-interactions/photoSelectionState";
import { adaptPhotoDetail } from "./photo-interactions/photoInteractionAdapters";
import { applyFaceAssignment, applyFaceDismissal } from "./face-labeling/faceLabelingState";
import { buildLibraryQueryForAlbum } from "./albums/albumLibraryQuery";
import { AlbumsGrid } from "./albums/AlbumsGrid";
import { useAlbumsRouteState } from "./albums/useAlbumsRouteState";
import type { AlbumRecord } from "./library/libraryRouteApi";

export function AlbumsRoutePage() {
  const navigate = useNavigate();
  const [selectionState, dispatchSelection] = useReducer(
    photoSelectionReducer,
    DEFAULT_PHOTO_SELECTION_STATE
  );
  const [photoInspectorState, dispatchPhotoInspector] = useReducer(
    photoInspectorReducer,
    DEFAULT_PHOTO_INSPECTOR_STATE
  );
  const [photoDetailById, setPhotoDetailById] = useState<Record<string, PhotoDetailPayload>>({});
  const [photoDetailErrorById, setPhotoDetailErrorById] = useState<Record<string, string>>({});
  const [loadingPhotoDetailId, setLoadingPhotoDetailId] = useState<string | null>(null);
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const {
    sortedAlbums,
    selectedAlbumId,
    detail,
    error,
    isLoading,
    createName,
    createType,
    createSavedFilterJsonDraft,
    isCreating,
    rowDrafts,
    savingAlbumId,
    deletingAlbumId,
    exportingAlbumId,
    exportProgress,
    canExport,
    handleCreateAlbum,
    handleSaveRow,
    handleDeleteRow,
    handleSelectRow,
    handleHideRow,
    handleRemovePhoto,
    handleExportAlbum,
    handleUpdateCreateName,
    handleUpdateCreateType,
    handleUpdateCreateSavedFilterJsonDraft,
    handleUpdateRowName,
    handleUpdateRowSavedFilterJsonDraft
  } = useAlbumsRouteState();

  useEffect(() => {
    let canceled = false;

    async function loadPeople() {
      try {
        const payload = await fetchPeopleDirectory();
        if (!canceled) {
          setPeopleDirectory(payload);
        }
      } catch {
        if (!canceled) {
          setPeopleDirectory([]);
        }
      }
    }

    void loadPeople();
    return () => {
      canceled = true;
    };
  }, []);

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
      .then((payload) => {
        if (!canceled) {
          setPhotoDetailById((current) => ({
            ...current,
            [activeInspectorPhotoId]: payload
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
          setLoadingPhotoDetailId((current) =>
            current === activeInspectorPhotoId ? null : current
          );
        }
      });

    return () => {
      canceled = true;
    };
  }, [activeInspectorPhotoId, photoDetailById]);

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
    if (!activeFaceAssignment) {
      return null;
    }
    const detailPayload = photoDetailById[activeFaceAssignment.photoId];
    return detailPayload ? adaptPhotoDetail(detailPayload) : null;
  }, [photoDetailById, photoInspectorState.activeFaceAssignment]);

  const activeFace = useMemo(() => {
    const activeFaceAssignment = photoInspectorState.activeFaceAssignment;
    if (!activeFaceAssignment || !activeFaceSummary) {
      return null;
    }
    return activeFaceSummary.faces.find((face) => face.faceId === activeFaceAssignment.faceId) ?? null;
  }, [activeFaceSummary, photoInspectorState.activeFaceAssignment]);

  useEffect(() => {
    if (!photoInspectorState.areFaceBoxesVisible || !detail || detail.items.length === 0) {
      return;
    }

    let canceled = false;
    const missingPhotoIds = detail.items
      .map((item) => item.photo_id)
      .filter((photoId) => !photoDetailById[photoId]);

    if (missingPhotoIds.length === 0) {
      return;
    }

    void Promise.all(
      missingPhotoIds.map(async (photoId) => {
        try {
          const payload = await fetchPhotoDetail(photoId);
          if (canceled) {
            return;
          }
          setPhotoDetailById((current) => (
            current[photoId]
              ? current
              : {
                  ...current,
                  [photoId]: payload
                }
          ));
        } catch {
          // Ignore prefetch failures; face overlays can still load when a card is inspected.
        }
      })
    );

    return () => {
      canceled = true;
    };
  }, [detail, photoDetailById, photoInspectorState.areFaceBoxesVisible]);

  const detailPhotoSummaryById = useMemo(() => {
    const summaries = new Map<string, ReturnType<typeof adaptPhotoDetail>>();
    if (!detail) {
      return summaries;
    }

    for (const item of detail.items) {
      const detailPayload = photoDetailById[item.photo_id];
      if (!detailPayload) {
        continue;
      }
      summaries.set(item.photo_id, adaptPhotoDetail(detailPayload));
    }

    return summaries;
  }, [detail, photoDetailById]);

  function handleOpenAlbum(album: AlbumRecord) {
    const query = buildLibraryQueryForAlbum(album);
    navigate(`/library${query ? `?${query}` : ""}`);
  }

  function handleToggleDetail(album: AlbumRecord) {
    if (selectedAlbumId === album.album_id) {
      handleHideRow();
      return;
    }
    void handleSelectRow(album.album_id, 1);
  }

  return (
    <section className="page albums-page" aria-labelledby="page-title">
      <header className="albums-header">
        <h1 id="page-title">Albums</h1>
        <p>Manage album CRUD directly in the grid. Select a row to inspect album photos.</p>
      </header>

      {error ? (
        <p className="albums-error" role="alert">
          {error}
        </p>
      ) : null}
      {isLoading ? <p className="albums-loading">Loading albums…</p> : null}

      <AlbumsGrid
        albums={sortedAlbums}
        selectedAlbumId={selectedAlbumId}
        detail={detail}
        detailPhotoSummaryById={detailPhotoSummaryById}
        selectedPhotoIds={selectionState.selectedPhotoIds}
        faceBoxesVisible={photoInspectorState.areFaceBoxesVisible}
        activeMetadataPhotoId={photoInspectorState.activeMetadataPhotoId}
        createName={createName}
        createType={createType}
        createSavedFilterJsonDraft={createSavedFilterJsonDraft}
        isCreating={isCreating}
        rowDrafts={rowDrafts}
        savingAlbumId={savingAlbumId}
        deletingAlbumId={deletingAlbumId}
        exportingAlbumId={exportingAlbumId}
        exportProgress={exportProgress}
        canExport={canExport}
        onCreateNameChange={handleUpdateCreateName}
        onCreateTypeChange={handleUpdateCreateType}
        onCreateSavedFilterJsonDraftChange={handleUpdateCreateSavedFilterJsonDraft}
        onCreateAlbum={() => void handleCreateAlbum()}
        onOpenAlbum={handleOpenAlbum}
        onToggleDetail={handleToggleDetail}
        onSave={(album) => void handleSaveRow(album)}
        onDelete={(album) => void handleDeleteRow(album)}
        onExport={(album) => void handleExportAlbum(album)}
        onRemovePhoto={(photoId) => void handleRemovePhoto(photoId)}
        onSelectPage={(albumId, page) => void handleSelectRow(albumId, page)}
        onRowNameChange={handleUpdateRowName}
        onRowSavedFilterJsonDraftChange={handleUpdateRowSavedFilterJsonDraft}
        onTogglePhotoSelected={(photoId) => {
          dispatchSelection({
            type: "togglePhotoSelection",
            photoId
          });
        }}
        onFaceBoxesVisibleChange={(visible) => {
          dispatchPhotoInspector({
            type: "setFaceBoxesVisible",
            visible
          });
        }}
        onOpenMetadata={(photoId, sourceSurfaceId) => {
          dispatchPhotoInspector({
            type: "openMetadata",
            photoId,
            sourceSurfaceId
          });
        }}
        onOpenFace={(photoId, faceId, sourceSurfaceId) => {
          dispatchPhotoInspector({
            type: "openFaceAssignment",
            photoId,
            faceId,
            sourceSurfaceId
          });
        }}
      />

      <PhotoMetadataFlyout
        isOpen={photoInspectorState.activeMetadataPhotoId !== null}
        summary={
          activeMetadataDetail
            ? {
                photoId: activeMetadataDetail.photo_id,
                title: activeMetadataDetail.photo_id,
                path: activeMetadataDetail.path,
                thumbnail: activeMetadataDetail.thumbnail
                  ? {
                      mimeType: activeMetadataDetail.thumbnail.mime_type,
                      width: activeMetadataDetail.thumbnail.width,
                      height: activeMetadataDetail.thumbnail.height,
                      dataBase64: activeMetadataDetail.thumbnail.data_base64
                    }
                  : null
              }
            : photoInspectorState.activeMetadataPhotoId
              ? {
                  photoId: photoInspectorState.activeMetadataPhotoId,
                  title: photoInspectorState.activeMetadataPhotoId,
                  path: photoInspectorState.activeMetadataPhotoId,
                  thumbnail: null
                }
              : null
        }
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
          display_name: person.display_name,
          created_ts: person.created_ts,
          updated_ts: person.updated_ts
        }))}
        onClose={() => dispatchPhotoInspector({ type: "closeFaceAssignment" })}
        onFaceUpdated={(faceId, personId) => {
          const activeFaceAssignment = photoInspectorState.activeFaceAssignment;
          if (!activeFaceAssignment) {
            return;
          }
          setPhotoDetailById((current) => {
            const existing = current[activeFaceAssignment.photoId];
            if (!existing) {
              return current;
            }
            return {
              ...current,
              [activeFaceAssignment.photoId]: applyFaceAssignment(existing, faceId, personId)
            };
          });
        }}
        onFaceDismissed={(faceId) => {
          const activeFaceAssignment = photoInspectorState.activeFaceAssignment;
          if (!activeFaceAssignment) {
            return;
          }
          setPhotoDetailById((current) => {
            const existing = current[activeFaceAssignment.photoId];
            if (!existing) {
              return current;
            }
            return {
              ...current,
              [activeFaceAssignment.photoId]: applyFaceDismissal(existing, faceId)
            };
          });
          dispatchPhotoInspector({ type: "closeFaceAssignment" });
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
                display_name: person.display_name,
                created_ts: person.created_ts ?? new Date().toISOString(),
                updated_ts: person.updated_ts ?? new Date().toISOString()
              }
            ];
          });
        }}
      />
    </section>
  );
}

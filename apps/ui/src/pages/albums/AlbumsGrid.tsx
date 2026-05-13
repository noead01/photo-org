import { Fragment } from "react";
import type { AlbumDetail, AlbumRecord } from "../library/libraryRouteApi";
import type { PhotoSummary } from "../photo-interactions/photoInteractionTypes";
import { serializeSavedFilter } from "./albumLibraryQuery";
import type { AlbumExportProgress, AlbumRowDraft } from "./useAlbumsRouteState";
import { AlbumDetailInline } from "./AlbumDetailInline";
import { AlbumsCreateRow } from "./AlbumsCreateRow";

interface AlbumsGridProps {
  albums: AlbumRecord[];
  selectedAlbumId: string | null;
  detail: AlbumDetail | null;
  detailPhotoSummaryById: Map<string, PhotoSummary>;
  selectedPhotoIds: Set<string>;
  faceBoxesVisible: boolean;
  activeMetadataPhotoId: string | null;
  createName: string;
  createType: "editable" | "saved_filter";
  createSavedFilterJsonDraft: string;
  isCreating: boolean;
  rowDrafts: Record<string, AlbumRowDraft>;
  savingAlbumId: string | null;
  deletingAlbumId: string | null;
  exportingAlbumId: string | null;
  exportProgress: AlbumExportProgress | null;
  canExport: boolean;
  onCreateNameChange: (value: string) => void;
  onCreateTypeChange: (value: "editable" | "saved_filter") => void;
  onCreateSavedFilterJsonDraftChange: (value: string) => void;
  onCreateAlbum: () => void;
  onOpenAlbum: (album: AlbumRecord) => void;
  onToggleDetail: (album: AlbumRecord) => void;
  onSave: (album: AlbumRecord) => void;
  onDelete: (album: AlbumRecord) => void;
  onExport: (album: AlbumRecord) => void;
  onRemovePhoto: (photoId: string) => void;
  onSelectPage: (albumId: string, page: number) => void;
  onRowNameChange: (albumId: string, value: string) => void;
  onRowSavedFilterJsonDraftChange: (albumId: string, value: string) => void;
  onTogglePhotoSelected: (photoId: string) => void;
  onFaceBoxesVisibleChange: (visible: boolean) => void;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string, faceIndex?: number) => void;
}

export function AlbumsGrid({
  albums,
  selectedAlbumId,
  detail,
  detailPhotoSummaryById,
  selectedPhotoIds,
  faceBoxesVisible,
  activeMetadataPhotoId,
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
  onCreateNameChange,
  onCreateTypeChange,
  onCreateSavedFilterJsonDraftChange,
  onCreateAlbum,
  onOpenAlbum,
  onToggleDetail,
  onSave,
  onDelete,
  onExport,
  onRemovePhoto,
  onSelectPage,
  onRowNameChange,
  onRowSavedFilterJsonDraftChange,
  onTogglePhotoSelected,
  onFaceBoxesVisibleChange,
  onOpenMetadata,
  onOpenFace
}: AlbumsGridProps) {
  return (
    <section className="albums-grid-shell" aria-label="Albums grid">
      <table className="albums-grid">
        <thead>
          <tr>
            <th scope="col">Album name</th>
            <th scope="col">Album type</th>
            <th scope="col">Saved filter or photo count</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          <AlbumsCreateRow
            createName={createName}
            createType={createType}
            createSavedFilterJsonDraft={createSavedFilterJsonDraft}
            isCreating={isCreating}
            onCreateNameChange={onCreateNameChange}
            onCreateTypeChange={onCreateTypeChange}
            onCreateSavedFilterJsonDraftChange={onCreateSavedFilterJsonDraftChange}
            onCreateAlbum={onCreateAlbum}
          />

          {albums.map((album) => {
            const draft = rowDrafts[album.album_id] ?? {
              name: album.name,
              savedFilterJsonDraft: serializeSavedFilter(album.saved_filter)
            };
            const isSaving = savingAlbumId === album.album_id;
            const isDeleting = deletingAlbumId === album.album_id;
            const isExporting = exportingAlbumId === album.album_id;
            const rowExportProgress =
              exportProgress && exportProgress.albumId === album.album_id
                ? exportProgress
                : null;

            return (
              <Fragment key={album.album_id}>
                <tr className={selectedAlbumId === album.album_id ? "is-selected" : undefined}>
                  <td>
                    <label className="visually-hidden" htmlFor={`album-name-${album.album_id}`}>
                      Album name for {album.name}
                    </label>
                    <input
                      id={`album-name-${album.album_id}`}
                      value={draft.name}
                      onChange={(event) => onRowNameChange(album.album_id, event.target.value)}
                    />
                  </td>
                  <td>
                    <span className={`albums-grid-kind albums-grid-kind-${album.kind}`}>{album.kind}</span>
                  </td>
                  <td>
                    {album.kind === "saved_filter" ? (
                      <>
                        <label className="visually-hidden" htmlFor={`album-filter-json-${album.album_id}`}>
                          Saved filter JSON for {album.name}
                        </label>
                        <textarea
                          id={`album-filter-json-${album.album_id}`}
                          value={draft.savedFilterJsonDraft}
                          onChange={(event) =>
                            onRowSavedFilterJsonDraftChange(album.album_id, event.target.value)
                          }
                        />
                      </>
                    ) : (
                      <span className="albums-grid-count">{album.item_count} photos</span>
                    )}
                  </td>
                  <td>
                    <div className="albums-grid-actions">
                      <button type="button" onClick={() => onOpenAlbum(album)}>
                        Open album {album.name}
                      </button>
                      <button type="button" onClick={() => onToggleDetail(album)}>
                        {selectedAlbumId === album.album_id
                          ? `Hide content ${album.name}`
                          : `Show content ${album.name}`}
                      </button>
                      <button type="button" onClick={() => onSave(album)} disabled={isSaving || isDeleting}>
                        {isSaving ? "Saving…" : "Save"}
                      </button>
                      <button type="button" onClick={() => onDelete(album)} disabled={isSaving || isDeleting}>
                        {isDeleting ? "Deleting…" : "Delete"}
                      </button>
                      {canExport ? (
                        <button
                          type="button"
                          onClick={() => onExport(album)}
                          disabled={isSaving || isDeleting || isExporting}
                        >
                          {isExporting ? "Exporting…" : `Export album ${album.name}`}
                        </button>
                      ) : null}
                    </div>
                    {rowExportProgress ? (
                      <div className="albums-export-progress" role="status" aria-live="polite">
                        <progress
                          aria-label={`Export progress for ${rowExportProgress.albumName}`}
                          max={rowExportProgress.totalCount}
                          value={rowExportProgress.completedCount}
                        />
                        <p>
                          Exporting {rowExportProgress.completedCount} of {rowExportProgress.totalCount} photos to "{rowExportProgress.folderLabel}".
                        </p>
                      </div>
                    ) : null}
                  </td>
                </tr>
                {selectedAlbumId === album.album_id ? (
                  <tr className="albums-grid-expanded-row">
                    <td colSpan={4}>
                      <AlbumDetailInline
                        detail={detail}
                        photoSummaryById={detailPhotoSummaryById}
                        selectedPhotoIds={selectedPhotoIds}
                        faceBoxesVisible={faceBoxesVisible}
                        activeMetadataPhotoId={activeMetadataPhotoId}
                        onRemovePhoto={onRemovePhoto}
                        onSelectPage={onSelectPage}
                        onTogglePhotoSelected={onTogglePhotoSelected}
                        onFaceBoxesVisibleChange={onFaceBoxesVisibleChange}
                        onOpenMetadata={onOpenMetadata}
                        onOpenFace={onOpenFace}
                      />
                    </td>
                  </tr>
                ) : null}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

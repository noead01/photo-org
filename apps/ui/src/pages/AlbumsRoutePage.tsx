import { useNavigate } from "react-router-dom";
import { buildLibraryQueryForAlbum } from "./albums/albumLibraryQuery";
import { AlbumsGrid } from "./albums/AlbumsGrid";
import { useAlbumsRouteState } from "./albums/useAlbumsRouteState";
import type { AlbumRecord } from "./library/libraryRouteApi";

export function AlbumsRoutePage() {
  const navigate = useNavigate();
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
    handleCreateAlbum,
    handleSaveRow,
    handleDeleteRow,
    handleSelectRow,
    handleHideRow,
    handleRemovePhoto,
    handleUpdateCreateName,
    handleUpdateCreateType,
    handleUpdateCreateSavedFilterJsonDraft,
    handleUpdateRowName,
    handleUpdateRowSavedFilterJsonDraft
  } = useAlbumsRouteState();

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
        createName={createName}
        createType={createType}
        createSavedFilterJsonDraft={createSavedFilterJsonDraft}
        isCreating={isCreating}
        rowDrafts={rowDrafts}
        savingAlbumId={savingAlbumId}
        deletingAlbumId={deletingAlbumId}
        onCreateNameChange={handleUpdateCreateName}
        onCreateTypeChange={handleUpdateCreateType}
        onCreateSavedFilterJsonDraftChange={handleUpdateCreateSavedFilterJsonDraft}
        onCreateAlbum={() => void handleCreateAlbum()}
        onOpenAlbum={handleOpenAlbum}
        onToggleDetail={handleToggleDetail}
        onSave={(album) => void handleSaveRow(album)}
        onDelete={(album) => void handleDeleteRow(album)}
        onRemovePhoto={(photoId) => void handleRemovePhoto(photoId)}
        onSelectPage={(albumId, page) => void handleSelectRow(albumId, page)}
        onRowNameChange={handleUpdateRowName}
        onRowSavedFilterJsonDraftChange={handleUpdateRowSavedFilterJsonDraft}
      />
    </section>
  );
}

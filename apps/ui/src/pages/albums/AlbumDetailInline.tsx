import type { AlbumDetail } from "../library/libraryRouteApi";
import { PhotoSurface } from "../photo-interactions/PhotoSurface";
import type { PhotoSummary } from "../photo-interactions/photoInteractionTypes";
import { formatDisplayPath } from "../suggestions/formatting";

interface AlbumDetailInlineProps {
  detail: AlbumDetail | null;
  photoSummaryById: Map<string, PhotoSummary>;
  selectedPhotoIds: Set<string>;
  faceBoxesVisible: boolean;
  activeMetadataPhotoId: string | null;
  onRemovePhoto: (photoId: string) => void;
  onSelectPage: (albumId: string, page: number) => void;
  onTogglePhotoSelected: (photoId: string) => void;
  onFaceBoxesVisibleChange: (visible: boolean) => void;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string, faceIndex?: number) => void;
}

function adaptAlbumItem(detail: AlbumDetail, item: AlbumDetail["items"][number]): PhotoSummary {
  return {
    photoId: item.photo_id,
    path: item.path,
    title: formatDisplayPath(item.path),
    shotTs: item.shot_ts,
    filesize: item.filesize,
    people: [],
    media: {
      thumbnail: item.thumbnail
        ? {
            mimeType: item.thumbnail.mime_type,
            width: item.thumbnail.width,
            height: item.thumbnail.height,
            dataBase64: item.thumbnail.data_base64
          }
        : null,
      originalIntent: "detail-only",
      originalAvailability: null
    },
    faces: [],
    albumMembership: {
      albumIds: [detail.album_id],
      currentAlbumId: detail.album_id
    },
    defaultFaceBoxesVisible: false
  };
}

export function AlbumDetailInline({
  detail,
  photoSummaryById,
  selectedPhotoIds,
  faceBoxesVisible,
  activeMetadataPhotoId,
  onRemovePhoto,
  onSelectPage,
  onTogglePhotoSelected,
  onFaceBoxesVisibleChange,
  onOpenMetadata,
  onOpenFace
}: AlbumDetailInlineProps) {
  return (
    <section className="albums-detail-inline" aria-label="Album detail">
      {detail ? (
        <>
          <div className="albums-detail-header">
            <div>
              <h2>{detail.name}</h2>
              <p>Type: {detail.kind}</p>
            </div>
          </div>

          {detail.items.length === 0 ? (
            <p className="albums-empty">No photos in this album.</p>
          ) : (
            <>
              <label className="albums-detail-face-boxes-toggle">
                <input
                  type="checkbox"
                  checked={faceBoxesVisible}
                  onChange={(event) => onFaceBoxesVisibleChange(event.currentTarget.checked)}
                />
                Show face boxes on all photos
              </label>
              <ul className="browse-grid albums-detail-grid" aria-label="Album photo thumbnails">
                {detail.items.map((item) => {
                  const hydratedSummary = photoSummaryById.get(item.photo_id);
                  const cardSummary = hydratedSummary
                    ? {
                        ...hydratedSummary,
                        title: formatDisplayPath(item.path),
                        albumMembership: {
                          albumIds: [detail.album_id],
                          currentAlbumId: detail.album_id
                        }
                      }
                    : adaptAlbumItem(detail, item);

                  return (
                    <li key={item.photo_id}>
                      <PhotoSurface
                        photo={cardSummary}
                        selected={selectedPhotoIds.has(item.photo_id)}
                        faceBoxesVisible={faceBoxesVisible}
                        activeMetadata={activeMetadataPhotoId === item.photo_id}
                        detailTo={`/library/${item.photo_id}`}
                        selectionLabel={`Select photo ${item.photo_id}`}
                        detailLabel={`Open details for ${item.path}`}
                        metadataLabel={`Show metadata for ${item.photo_id}`}
                        onToggleSelected={onTogglePhotoSelected}
                        onOpenMetadata={onOpenMetadata}
                        onOpenFace={onOpenFace}
                      />
                      {detail.kind === "editable" ? (
                        <button
                          type="button"
                          className="albums-detail-remove-photo-badge"
                          aria-label={`Remove photo ${item.photo_id}`}
                          title={`Remove photo ${item.photo_id}`}
                          onClick={() => onRemovePhoto(item.photo_id)}
                        >
                          <span aria-hidden="true">×</span>
                        </button>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
          {detail.total_pages > 1 ? (
            <div className="albums-detail-pagination" aria-label="Album content pagination">
              <button
                type="button"
                className="albums-button"
                onClick={() => {
                  if (detail.page > 1) {
                    onSelectPage(detail.album_id, detail.page - 1);
                  }
                }}
                disabled={detail.page <= 1}
              >
                Previous page
              </button>
              <p>
                Page {detail.page} of {detail.total_pages}
              </p>
              <button
                type="button"
                className="albums-button"
                onClick={() => {
                  if (detail.page < detail.total_pages) {
                    onSelectPage(detail.album_id, detail.page + 1);
                  }
                }}
                disabled={detail.page >= detail.total_pages}
              >
                Next page
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <p className="albums-empty">Loading album details…</p>
      )}
    </section>
  );
}

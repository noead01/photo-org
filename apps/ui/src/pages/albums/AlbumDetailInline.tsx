import type { AlbumDetail } from "../library/libraryRouteApi";

interface AlbumDetailInlineProps {
  detail: AlbumDetail | null;
  onRemovePhoto: (photoId: string) => void;
  onSelectPage: (albumId: string, page: number) => void;
}

export function AlbumDetailInline({ detail, onRemovePhoto, onSelectPage }: AlbumDetailInlineProps) {
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
            <ul className="albums-detail-grid" aria-label="Album photo thumbnails">
              {detail.items.map((item) => (
                <li key={item.photo_id}>
                  {item.thumbnail ? (
                    <img
                      className="albums-detail-thumb"
                      src={`data:${item.thumbnail.mime_type};base64,${item.thumbnail.data_base64}`}
                      width={item.thumbnail.width}
                      height={item.thumbnail.height}
                      alt={item.path}
                    />
                  ) : (
                    <div className="albums-detail-thumb albums-detail-thumb-placeholder" aria-hidden="true">
                      No preview
                    </div>
                  )}
                  <p title={item.path}>{item.path}</p>
                  {detail.kind === "editable" ? (
                    <button type="button" onClick={() => onRemovePhoto(item.photo_id)}>
                      Remove photo {item.photo_id}
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {detail.total_pages > 1 ? (
            <div className="albums-detail-pagination" aria-label="Album content pagination">
              <button
                type="button"
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

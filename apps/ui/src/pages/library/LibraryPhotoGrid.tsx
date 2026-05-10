import { AlbumActionSurface } from "../photo-interactions/AlbumActionSurface";
import { adaptLibraryPhoto } from "../photo-interactions/photoInteractionAdapters";
import { PhotoSurface } from "../photo-interactions/PhotoSurface";
import type { AlbumTarget } from "../photo-interactions/photoInteractionTypes";
import type { LibraryPhoto } from "./libraryRouteTypes";
import type { serializeLibrarySelectionState } from "./librarySelection";

interface LibraryPhotoGridProps {
  photos: LibraryPhoto[];
  photoSummaryById: Map<string, ReturnType<typeof adaptLibraryPhoto>>;
  locationSearch: string;
  selectionRouteState: ReturnType<typeof serializeLibrarySelectionState>;
  selectedPhotoIds: Set<string>;
  onTogglePhotoSelection: (photoId: string) => void;
  faceBoxesVisible: boolean;
  activeMetadataPhotoId: string | null;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string, faceIndex?: number) => void;
  albumAssignmentWidgetsVisible: boolean;
  albumTargets: AlbumTarget[];
  albumActionResultByPhotoId: Record<string, string>;
  isAlbumActionSubmitting: boolean;
  onAddSinglePhotoToAlbum: (photoId: string, albumId: string) => void;
  onCreateAlbumAndAddSinglePhoto: (photoId: string, albumName: string) => void;
  libraryViewRouteState: {
    sortDirection: "asc" | "desc";
    page: number;
    pageSize: number;
  };
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

export function LibraryPhotoGrid({
  photos,
  photoSummaryById,
  locationSearch,
  selectionRouteState,
  selectedPhotoIds,
  onTogglePhotoSelection,
  libraryViewRouteState,
  faceBoxesVisible,
  activeMetadataPhotoId,
  onOpenMetadata,
  onOpenFace,
  albumAssignmentWidgetsVisible,
  albumTargets,
  albumActionResultByPhotoId,
  isAlbumActionSubmitting,
  onAddSinglePhotoToAlbum,
  onCreateAlbumAndAddSinglePhoto
}: LibraryPhotoGridProps) {
  return (
    <ol className="browse-grid" aria-label="Photo gallery">
      {photos.map((photo) => {
        const summary = photoSummaryById.get(photo.photo_id) ?? adaptLibraryPhoto(photo);
        const displayPath = formatDisplayPath(photo.path);
        return (
          <li key={photo.photo_id}>
            <PhotoSurface
              photo={{
                ...summary,
                title: displayPath
              }}
              selected={selectedPhotoIds.has(photo.photo_id)}
              faceBoxesVisible={faceBoxesVisible}
              activeMetadata={activeMetadataPhotoId === photo.photo_id}
              detailTo={`/library/${photo.photo_id}`}
              detailState={{
                returnToLibrarySearch: locationSearch,
                returnFocusPhotoId: photo.photo_id,
                librarySelection: selectionRouteState,
                libraryViewState: libraryViewRouteState
              }}
              selectionLabel={`Select photo ${photo.photo_id}`}
              detailLabel={`Open details for ${photo.path}`}
              metadataLabel={`Show metadata for ${summary.title}`}
              albumAssignmentWidget={
                albumAssignmentWidgetsVisible ? (
                  <AlbumActionSurface
                    albums={albumTargets}
                    selectedPhotoIds={[photo.photo_id]}
                    isSubmitting={isAlbumActionSubmitting}
                    resultMessage={albumActionResultByPhotoId[photo.photo_id] ?? null}
                    onAddToAlbum={(albumId) => {
                      onAddSinglePhotoToAlbum(photo.photo_id, albumId);
                    }}
                    onCreateAlbumAndAdd={(name) => {
                      onCreateAlbumAndAddSinglePhoto(photo.photo_id, name);
                    }}
                  />
                ) : null
              }
              onToggleSelected={onTogglePhotoSelection}
              onOpenMetadata={onOpenMetadata}
              onOpenFace={onOpenFace}
            />
          </li>
        );
      })}
    </ol>
  );
}

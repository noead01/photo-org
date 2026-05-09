import { adaptLibraryPhoto } from "../photo-interactions/photoInteractionAdapters";
import { PhotoSurface } from "../photo-interactions/PhotoSurface";
import type { LibraryPhoto } from "./libraryRouteTypes";
import type { serializeLibrarySelectionState } from "./librarySelection";

interface LibraryPhotoGridProps {
  photos: LibraryPhoto[];
  locationSearch: string;
  selectionRouteState: ReturnType<typeof serializeLibrarySelectionState>;
  selectedPhotoIds: Set<string>;
  onTogglePhotoSelection: (photoId: string) => void;
  faceBoxesVisible: boolean;
  activeMetadataPhotoId: string | null;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (photoId: string, faceId: string, sourceSurfaceId: string) => void;
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

function summarizePhotoFaces(photo: LibraryPhoto): {
  detectedFaces: number;
  assignedFaces: number;
  suggestedFaces: number;
} {
  const faces = photo.faces ?? [];
  let assignedFaces = 0;
  let suggestedFaces = 0;

  faces.forEach((face) => {
    if (face.person_id) {
      assignedFaces += 1;
    }

    if (face.person_id === null) {
      const hasSuggestions =
        (face.suggestions?.length ?? 0) > 0
        || (face.label_source === "machine_suggested" && typeof face.confidence === "number");
      if (hasSuggestions) {
        suggestedFaces += 1;
      }
    }
  });

  return {
    detectedFaces: faces.length,
    assignedFaces,
    suggestedFaces
  };
}

function formatFaceSummary(metrics: ReturnType<typeof summarizePhotoFaces>): string {
  const base = `Faces detected/assigned: ${metrics.detectedFaces}/${metrics.assignedFaces}`;
  if (metrics.suggestedFaces <= 0) {
    return base;
  }
  const noun = metrics.suggestedFaces === 1 ? "suggestion" : "suggestions";
  return `${base} - ${metrics.suggestedFaces} ${noun}`;
}

export function LibraryPhotoGrid({
  photos,
  locationSearch,
  selectionRouteState,
  selectedPhotoIds,
  onTogglePhotoSelection,
  libraryViewRouteState,
  faceBoxesVisible,
  activeMetadataPhotoId,
  onOpenMetadata,
  onOpenFace
}: LibraryPhotoGridProps) {
  return (
    <ol className="browse-grid" aria-label="Photo gallery">
      {photos.map((photo) => {
        const summary = adaptLibraryPhoto(photo);
        const displayPath = formatDisplayPath(photo.path);
        const faceSummary = formatFaceSummary(summarizePhotoFaces(photo));
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
              supportingText={faceSummary}
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

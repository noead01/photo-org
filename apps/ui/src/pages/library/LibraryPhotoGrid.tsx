import { Link } from "react-router-dom";
import type { LibraryPhoto } from "./libraryRouteTypes";
import type { serializeLibrarySelectionState } from "./librarySelection";

interface LibraryPhotoGridProps {
  photos: LibraryPhoto[];
  locationSearch: string;
  selectionRouteState: ReturnType<typeof serializeLibrarySelectionState>;
  selectedPhotoIds: Set<string>;
  onTogglePhotoSelection: (photoId: string) => void;
  libraryViewRouteState: {
    sortDirection: "asc" | "desc";
    cursorByPage: Record<number, string | null>;
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
  humanAssignedPeople: number;
  machineSuggestedFaces: number;
} {
  const faces = photo.faces ?? [];
  const humanPeople = new Set<string>();
  let machineSuggestedFaces = 0;

  faces.forEach((face) => {
    if (face.label_source === "human_confirmed" && face.person_id) {
      humanPeople.add(face.person_id);
    }
    if (face.label_source === "machine_suggested" && typeof face.confidence === "number") {
      machineSuggestedFaces += 1;
    }
  });

  return {
    detectedFaces: faces.length,
    humanAssignedPeople: humanPeople.size,
    machineSuggestedFaces
  };
}

export function LibraryPhotoGrid({
  photos,
  locationSearch,
  selectionRouteState,
  selectedPhotoIds,
  onTogglePhotoSelection,
  libraryViewRouteState
}: LibraryPhotoGridProps) {
  return (
    <ol className="browse-grid" aria-label="Photo gallery">
      {photos.map((photo) => {
        const metrics = summarizePhotoFaces(photo);
        const displayPath = formatDisplayPath(photo.path);
        const isSelected = selectedPhotoIds.has(photo.photo_id);
        return (
          <li
            key={photo.photo_id}
            className={`browse-card${isSelected ? " browse-card-selected" : ""}`}
          >
            <label className="browse-card-checkbox-badge">
              <input
                type="checkbox"
                checked={isSelected}
                aria-label={`Select photo ${photo.photo_id}`}
                onChange={() => {
                  onTogglePhotoSelection(photo.photo_id);
                }}
              />
            </label>
            <div className="browse-thumbnail-shell">
            <Link
              className="browse-thumbnail-link"
              data-photo-id={photo.photo_id}
              to={`/library/${photo.photo_id}`}
              state={{
                returnToLibrarySearch: locationSearch,
                returnFocusPhotoId: photo.photo_id,
                librarySelection: selectionRouteState,
                libraryViewState: libraryViewRouteState
              }}
              aria-label={`Open details for ${photo.path}`}
            >
              {photo.thumbnail ? (
                <img
                  className="browse-thumbnail"
                  src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                  width={photo.thumbnail.width}
                  height={photo.thumbnail.height}
                  alt={`Preview of ${photo.path}`}
                />
              ) : (
                <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                  No preview
                </div>
              )}
            </Link>
            </div>
            <div className="browse-card-body">
              <p className="browse-path" title={photo.path}>
                {displayPath}
              </p>
              <dl className="browse-card-metrics">
                <div>
                  <dt>Faces detected</dt>
                  <dd>{metrics.detectedFaces}</dd>
                </div>
                <div>
                  <dt>People assigned (human)</dt>
                  <dd>{metrics.humanAssignedPeople}</dd>
                </div>
                <div>
                  <dt>Machine suggestions</dt>
                  <dd>{metrics.machineSuggestedFaces}</dd>
                </div>
              </dl>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

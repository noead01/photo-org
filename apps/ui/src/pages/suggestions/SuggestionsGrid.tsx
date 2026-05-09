import { adaptSuggestionPhoto } from "../photo-interactions/photoInteractionAdapters";
import { PhotoSurface } from "../photo-interactions/PhotoSurface";
import { formatDisplayPath } from "./formatting";
import { SuggestionFaceRow } from "./SuggestionFaceRow";
import type { SuggestionPhoto, SuggestedFace } from "./types";

type SuggestionsGridProps = {
  items: SuggestionPhoto[];
  selectedPhotoIds: Set<string>;
  selectedFaceIds: Set<string>;
  faceBoxesVisible: boolean;
  activeMetadataPhotoId: string | null;
  faceActionInFlightIds: Set<string>;
  faceChoiceDrafts: Map<string, string>;
  isLoading: boolean;
  isConfirming: boolean;
  onTogglePhotoSelected: (photoId: string) => void;
  onToggleFaceSelected: (faceId: string) => void;
  onFaceChoiceChange: (faceId: string, value: string) => void;
  onOpenMetadata: (photoId: string, sourceSurfaceId: string) => void;
  onOpenFace: (face: SuggestedFace, photoId: string, sourceSurfaceId: string) => void;
  onConfirmSingleFace: (face: SuggestedFace) => void;
  onMarkFaceUnknown: (face: SuggestedFace) => void;
  onDismissFalsePositive: (face: SuggestedFace) => void;
};

export function SuggestionsGrid({
  items,
  selectedPhotoIds,
  selectedFaceIds,
  faceBoxesVisible,
  activeMetadataPhotoId,
  faceActionInFlightIds,
  faceChoiceDrafts,
  isLoading,
  isConfirming,
  onTogglePhotoSelected,
  onToggleFaceSelected,
  onFaceChoiceChange,
  onOpenMetadata,
  onOpenFace,
  onConfirmSingleFace,
  onMarkFaceUnknown,
  onDismissFalsePositive,
}: SuggestionsGridProps) {
  return (
    <ol className="suggestions-grid" aria-label="Suggestion photo list">
      {items.map((photo) => {
        const summary = adaptSuggestionPhoto(photo);
        const displayPath = formatDisplayPath(photo.path);
        const numberedFaces = photo.faces.map((face, index) => ({
          ...face,
          faceNumber: index + 1,
        }));
        const faceById = new Map(numberedFaces.map((face) => [face.face_id, face] as const));
        const suggestionCount = photo.faces.length;
        const suggestionLabel = `${suggestionCount} pending face${suggestionCount === 1 ? "" : "s"}`;

        return (
          <li key={photo.photo_id} className="suggestions-card">
            <div className="suggestions-photo-surface">
              <PhotoSurface
                photo={{
                  ...summary,
                  title: displayPath
                }}
                selected={selectedPhotoIds.has(photo.photo_id)}
                faceBoxesVisible={faceBoxesVisible}
                activeMetadata={activeMetadataPhotoId === photo.photo_id}
                detailTo={`/library/${photo.photo_id}`}
                selectionLabel={`Select photo ${photo.photo_id}`}
                detailLabel={`Open details for ${photo.path}`}
                metadataLabel={`Show metadata for ${summary.title}`}
                supportingText={suggestionLabel}
                onToggleSelected={onTogglePhotoSelected}
                onOpenMetadata={onOpenMetadata}
                onOpenFace={(_photoId, faceId, sourceSurfaceId) => {
                  const selectedFace = faceById.get(faceId);
                  if (selectedFace) {
                    onOpenFace(selectedFace, photo.photo_id, sourceSurfaceId);
                  }
                }}
              />
            </div>
            <div className="suggestions-card-body">
              <ul className="suggestions-face-list">
                {numberedFaces.map((face) => (
                  <SuggestionFaceRow
                    key={face.face_id}
                    face={face}
                    faceNumber={face.faceNumber}
                    isSelected={selectedFaceIds.has(face.face_id)}
                    isLoading={isLoading}
                    isConfirming={isConfirming}
                    isFaceActionInFlight={faceActionInFlightIds.has(face.face_id)}
                    choiceDraft={faceChoiceDrafts.get(face.face_id) ?? face.top_suggestion.display_name}
                    onToggleSelected={onToggleFaceSelected}
                    onChoiceChange={onFaceChoiceChange}
                    onConfirmFace={onConfirmSingleFace}
                    onMarkUnknown={onMarkFaceUnknown}
                    onDismissFalsePositive={onDismissFalsePositive}
                  />
                ))}
              </ul>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

import { Link } from "react-router-dom";
import { FaceBBoxOverlay, buildFaceOverlayRegions } from "../FaceBBoxOverlay";
import { buildFaceZoomStyle, formatDisplayPath } from "./formatting";
import { SuggestionFaceRow } from "./SuggestionFaceRow";
import type { SuggestionPhoto, SuggestedFace } from "./types";

type SuggestionsGridProps = {
  items: SuggestionPhoto[];
  selectedFaceIds: Set<string>;
  faceActionInFlightIds: Set<string>;
  faceChoiceDrafts: Map<string, string>;
  isLoading: boolean;
  isConfirming: boolean;
  onToggleFaceSelected: (faceId: string) => void;
  onFaceChoiceChange: (faceId: string, value: string) => void;
  onConfirmSingleFace: (face: SuggestedFace) => void;
  onMarkFaceUnknown: (face: SuggestedFace) => void;
  onDismissFalsePositive: (face: SuggestedFace) => void;
};

export function SuggestionsGrid({
  items,
  selectedFaceIds,
  faceActionInFlightIds,
  faceChoiceDrafts,
  isLoading,
  isConfirming,
  onToggleFaceSelected,
  onFaceChoiceChange,
  onConfirmSingleFace,
  onMarkFaceUnknown,
  onDismissFalsePositive,
}: SuggestionsGridProps) {
  return (
    <ol className="suggestions-grid" aria-label="Suggestion photo list">
      {items.map((photo) => {
        const numberedFaces = photo.faces.map((face, index) => ({
          ...face,
          faceNumber: index + 1,
        }));
        const faceById = new Map(numberedFaces.map((face) => [face.face_id, face] as const));
        const faceNumberById = new Map(
          numberedFaces.map((face) => [face.face_id, face.faceNumber] as const)
        );
        const overlayRegions = photo.thumbnail
          ? buildFaceOverlayRegions(
              numberedFaces.map((face) => ({
                face_id: face.face_id,
                person_id: null,
                bbox_x: face.bbox_x ?? null,
                bbox_y: face.bbox_y ?? null,
                bbox_w: face.bbox_w ?? null,
                bbox_h: face.bbox_h ?? null,
                bbox_space_width: face.bbox_space_width ?? null,
                bbox_space_height: face.bbox_space_height ?? null,
              })),
              photo.thumbnail.width,
              photo.thumbnail.height
            )
          : [];
        const thumbnailShellStyle = photo.thumbnail
          ? { aspectRatio: `${photo.thumbnail.width} / ${photo.thumbnail.height}` }
          : undefined;

        return (
          <li key={photo.photo_id} className="suggestions-card">
            <div className="suggestions-thumbnail-shell" style={thumbnailShellStyle}>
              <Link
                className="suggestions-thumbnail-link"
                to={`/library/${photo.photo_id}`}
                aria-label={`Open details for ${photo.path}`}
              >
                {photo.thumbnail ? (
                  <img
                    className="suggestions-thumbnail"
                    src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                    width={photo.thumbnail.width}
                    height={photo.thumbnail.height}
                    alt={`Preview of ${photo.path}`}
                  />
                ) : (
                  <div className="suggestions-thumbnail suggestions-thumbnail-placeholder" aria-hidden="true">
                    No preview
                  </div>
                )}
                <FaceBBoxOverlay
                  regions={overlayRegions}
                  allowRegionHover
                  ariaLabel={`Suggested face regions for ${photo.path}`}
                  renderRegionContent={(region) => {
                    const matchingFace = faceById.get(region.faceId);
                    const zoomStyle =
                      photo.thumbnail && matchingFace
                        ? buildFaceZoomStyle(region, photo.thumbnail)
                        : null;
                    return (
                      <span className="suggestions-face-overlay-marker" aria-hidden="true">
                        <span className="suggestions-face-overlay-badge">
                          {faceNumberById.get(region.faceId) ?? "?"}
                        </span>
                        {photo.thumbnail && zoomStyle ? (
                          <span className="suggestions-face-overlay-zoom" style={zoomStyle.frame}>
                            <img
                              src={`data:${photo.thumbnail.mime_type};base64,${photo.thumbnail.data_base64}`}
                              width={photo.thumbnail.width}
                              height={photo.thumbnail.height}
                              style={zoomStyle.image}
                              alt=""
                            />
                          </span>
                        ) : null}
                      </span>
                    );
                  }}
                />
              </Link>
            </div>
            <div className="suggestions-card-body">
              <p className="suggestions-path" title={photo.path}>
                {formatDisplayPath(photo.path)}
              </p>
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

import type { CSSProperties } from "react";
import {
  FaceBBoxOverlay,
  type FaceOverlayRegion,
} from "../FaceBBoxOverlay";

type IngestStatus = {
  tone: "complete" | "pending" | "failed" | "unknown";
  label: string;
  description: string;
} | null;

interface PhotoPreviewPanelProps {
  detailPhotoId: string;
  selected: boolean;
  previewImageSrc: string | null;
  shouldUseOriginalImage: boolean;
  activeOriginalImageSrc: string | null;
  thumbnailSize: { width: number; height: number } | null;
  ingestStatus: IngestStatus;
  showFaceBoxes: boolean;
  imageScalePercent: number;
  faceOverlayRegions: FaceOverlayRegion[];
  faceBadgeInitialsById: Map<string, string>;
  faceRegionState: string;
  onToggleSelected: (photoId: string) => void;
  onShowFaceBoxesChange: (checked: boolean) => void;
  onImageScalePercentChange: (value: number) => void;
  onToggleDetails: () => void;
  isDetailFlyoutOpen: boolean;
  onOpenFaceAssignment: (faceId: string) => void;
  onImageLoad: (image: HTMLImageElement) => void;
  onImageError: (image: HTMLImageElement) => void;
}

export function PhotoPreviewPanel({
  detailPhotoId,
  selected,
  previewImageSrc,
  shouldUseOriginalImage,
  activeOriginalImageSrc,
  thumbnailSize,
  ingestStatus,
  showFaceBoxes,
  imageScalePercent,
  faceOverlayRegions,
  faceBadgeInitialsById,
  faceRegionState,
  onToggleSelected,
  onShowFaceBoxesChange,
  onImageScalePercentChange,
  onToggleDetails,
  isDetailFlyoutOpen,
  onOpenFaceAssignment,
  onImageLoad,
  onImageError,
}: PhotoPreviewPanelProps) {
  const mediaStageStyle: CSSProperties = { width: `${Math.max(25, imageScalePercent)}%` };

  return (
    <article className="detail-preview-panel">
      <h2>Preview</h2>
      <div className="detail-media-controls" role="group" aria-label="Preview controls">
        <label className="detail-photo-select-toggle">
          <input
            type="checkbox"
            aria-label="Select photo"
            checked={selected}
            onChange={() => onToggleSelected(detailPhotoId)}
          />
          Select photo
        </label>
        <label className="detail-face-box-toggle">
          <input
            type="checkbox"
            aria-label="Show face boxes"
            checked={showFaceBoxes}
            onChange={(event) => onShowFaceBoxesChange(event.currentTarget.checked)}
          />
          Show face boxes
        </label>
        <label className="detail-photo-scale">
          <span>Photo size</span>
          <input
            type="range"
            min={25}
            max={225}
            step={5}
            value={imageScalePercent}
            aria-label="Photo size"
            onChange={(event) => onImageScalePercentChange(Number(event.currentTarget.value))}
          />
          <span>{imageScalePercent}%</span>
        </label>
        <button type="button" onClick={onToggleDetails}>
          {isDetailFlyoutOpen ? "Hide details" : "Show details"}
        </button>
      </div>
      {ingestStatus ? (
        <p className="detail-ingest-inline">
          <span className={`ingest-status-badge is-${ingestStatus.tone}`}>{ingestStatus.label}</span>
          <span>{ingestStatus.description}</span>
        </p>
      ) : null}
      {previewImageSrc ? (
        <div className="detail-media-frame">
          <div className="detail-media-stage" style={mediaStageStyle}>
            <img
              className="detail-media-image"
              src={previewImageSrc}
              width={!shouldUseOriginalImage ? thumbnailSize?.width : undefined}
              height={!shouldUseOriginalImage ? thumbnailSize?.height : undefined}
              alt={`Preview for ${detailPhotoId}`}
              onLoad={(event) => {
                if (!activeOriginalImageSrc && shouldUseOriginalImage) {
                  return;
                }
                onImageLoad(event.currentTarget);
              }}
              onError={(event) => {
                if (!activeOriginalImageSrc && shouldUseOriginalImage) {
                  return;
                }
                onImageError(event.currentTarget);
              }}
            />
            {showFaceBoxes ? (
              <FaceBBoxOverlay
                regions={faceOverlayRegions}
                ariaLabel="Detected face regions"
                onRegionClick={(region) => {
                  onOpenFaceAssignment(region.faceId);
                }}
                renderRegionContent={(region, index) => (
                  <button
                    type="button"
                    className="detail-face-overlay-provenance-button"
                    aria-label={`Open face assignment for face region ${index + 1}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      onOpenFaceAssignment(region.faceId);
                    }}
                  >
                    {faceBadgeInitialsById.get(region.faceId) ?? "?"}
                  </button>
                )}
              />
            ) : null}
          </div>
        </div>
      ) : (
        <div className="detail-preview-placeholder" aria-hidden="true">
          No preview
        </div>
      )}
      <p className="detail-face-state">{faceRegionState}</p>
    </article>
  );
}

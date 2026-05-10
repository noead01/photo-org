import { FaceBBoxOverlay, buildFaceOverlayRegions } from "../FaceBBoxOverlay";
import "./photo-interactions.css";
import type { PhotoFace } from "./photoInteractionTypes";
import { buildFaceActionSummary, resolveFaceConfidenceIndicator } from "./faceActionSummary";

interface FaceOverlayLayerProps {
  faces: PhotoFace[];
  thumbnailSize: { width: number; height: number } | null;
  visible: boolean;
  onOpenFace: (faceId: string, faceIndex: number) => void;
}

export function FaceOverlayLayer({
  faces,
  thumbnailSize,
  visible,
  onOpenFace,
}: FaceOverlayLayerProps) {
  if (!visible || !thumbnailSize) {
    return null;
  }

  const regions = buildFaceOverlayRegions(
    faces.map((face) => ({
      face_id: face.faceId,
      person_id: face.personId,
      bbox_x: face.bbox.x,
      bbox_y: face.bbox.y,
      bbox_w: face.bbox.width,
      bbox_h: face.bbox.height,
      bbox_space_width: face.bbox.spaceWidth,
      bbox_space_height: face.bbox.spaceHeight,
      label_source: face.labelSource,
    })),
    thumbnailSize.width,
    thumbnailSize.height
  );
  const faceById = new Map(faces.map((face) => [face.faceId, face] as const));

  function renderFaceIndicator(face: PhotoFace) {
    const indicator = resolveFaceConfidenceIndicator(face);
    if (indicator === "assigned") {
      return <span className="photo-face-confidence-indicator is-assigned" aria-hidden="true">✓</span>;
    }
    if (indicator === "unknown") {
      return <span className="photo-face-confidence-indicator is-unknown" aria-hidden="true">?</span>;
    }

    const level = indicator === "low" ? 1 : indicator === "medium" ? 2 : indicator === "strong" ? 3 : 0;
    return (
      <span className={`photo-face-confidence-indicator is-battery is-${indicator}`} aria-hidden="true">
        <span className="photo-face-battery-shell">
          <span className={`photo-face-battery-cell ${level >= 1 ? "is-filled" : ""}`} />
          <span className={`photo-face-battery-cell ${level >= 2 ? "is-filled" : ""}`} />
          <span className={`photo-face-battery-cell ${level >= 3 ? "is-filled" : ""}`} />
        </span>
        <span className="photo-face-battery-tip" />
      </span>
    );
  }

  function renderFaceChipContent(face: PhotoFace) {
    const label = buildFaceActionSummary(face);
    return (
      <>
        {renderFaceIndicator(face)}
        {label ? <span className="photo-face-chip-label">{label}</span> : null}
      </>
    );
  }

  if (regions.length === 0 && faces.length > 0) {
    return (
      <ol className="photo-face-fallback-list" aria-label="Detected face regions">
        {faces.map((face, index) => (
          <li key={face.faceId}>
            <button
              type="button"
              className="photo-face-fallback-chip-button"
              aria-label={`Open face ${index + 1} actions`}
              onClick={(event) => {
                event.stopPropagation();
                onOpenFace(face.faceId, index);
              }}
            >
              {renderFaceChipContent(face)}
            </button>
          </li>
        ))}
      </ol>
    );
  }

  return (
    <FaceBBoxOverlay
      regions={regions}
      allowRegionHover
      ariaLabel="Detected face regions"
      onRegionClick={(region, index) => onOpenFace(region.faceId, index)}
      renderRegionContent={(region, index) => (
        <button
          type="button"
          className="photo-face-region-chip-button"
          aria-label={`Open face ${index + 1} actions`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenFace(region.faceId, index);
          }}
        >
          {renderFaceChipContent(faceById.get(region.faceId) ?? faces[index] ?? faces[0]!)}
        </button>
      )}
    />
  );
}

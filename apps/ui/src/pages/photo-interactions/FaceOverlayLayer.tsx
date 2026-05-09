import { FaceBBoxOverlay, buildFaceOverlayRegions } from "../FaceBBoxOverlay";
import type { PhotoFace } from "./photoInteractionTypes";

interface FaceOverlayLayerProps {
  faces: PhotoFace[];
  thumbnailSize: { width: number; height: number } | null;
  visible: boolean;
  onOpenFace: (faceId: string) => void;
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

  return (
    <FaceBBoxOverlay
      regions={regions}
      allowRegionHover
      ariaLabel="Detected face regions"
      onRegionClick={(region) => onOpenFace(region.faceId)}
      renderRegionContent={(region, index) => (
        <button
          type="button"
          className="photo-face-region-button"
          aria-label={`Open face ${index + 1} actions`}
          onClick={(event) => {
            event.stopPropagation();
            onOpenFace(region.faceId);
          }}
        >
          {index + 1}
        </button>
      )}
    />
  );
}

import type { ReactNode } from "react";

export type FaceLabelSource = "human_confirmed" | "machine_applied" | "machine_suggested" | null;

export type FaceBBoxOverlayFace = {
  face_id: string;
  person_id: string | null;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
  label_source?: FaceLabelSource;
};

export type FaceOverlayRegion = {
  faceId: string;
  personId: string | null;
  labelSource: FaceLabelSource;
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
};

interface FaceBBoxOverlayProps {
  regions: FaceOverlayRegion[];
  ariaLabel: string;
  getRegionAriaLabel?: (region: FaceOverlayRegion, index: number) => string;
  renderRegionContent?: (region: FaceOverlayRegion, index: number) => ReactNode;
  onRegionClick?: (region: FaceOverlayRegion, index: number) => void;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function inferFaceOverlayCoordinateSpace(
  faces: FaceBBoxOverlayFace[],
  thumbnailWidth: number,
  thumbnailHeight: number
): { width: number; height: number } {
  const explicitCoordinateSpace = faces.reduce(
    (acc, face) => {
      if (
        face.bbox_space_width !== null &&
        face.bbox_space_width !== undefined &&
        face.bbox_space_height !== null &&
        face.bbox_space_height !== undefined &&
        face.bbox_space_width > 0 &&
        face.bbox_space_height > 0
      ) {
        acc.width = Math.max(acc.width, face.bbox_space_width);
        acc.height = Math.max(acc.height, face.bbox_space_height);
      }
      return acc;
    },
    { width: 0, height: 0 }
  );

  if (explicitCoordinateSpace.width > 0 && explicitCoordinateSpace.height > 0) {
    return explicitCoordinateSpace;
  }

  // Fallback for legacy records without explicit coordinate-space dimensions.
  const coordinateSpace = faces.reduce(
    (acc, face) => {
      if (
        face.bbox_x === null ||
        face.bbox_y === null ||
        face.bbox_w === null ||
        face.bbox_h === null ||
        face.bbox_w <= 0 ||
        face.bbox_h <= 0
      ) {
        return acc;
      }

      acc.width = Math.max(acc.width, face.bbox_x + face.bbox_w);
      acc.height = Math.max(acc.height, face.bbox_y + face.bbox_h);
      return acc;
    },
    { width: thumbnailWidth, height: thumbnailHeight }
  );

  return {
    width: Math.max(coordinateSpace.width, thumbnailWidth),
    height: Math.max(coordinateSpace.height, thumbnailHeight)
  };
}

export function buildFaceOverlayRegions(
  faces: FaceBBoxOverlayFace[],
  thumbnailWidth: number,
  thumbnailHeight: number
): FaceOverlayRegion[] {
  if (thumbnailWidth <= 0 || thumbnailHeight <= 0) {
    return [];
  }

  const coordinateSpace = inferFaceOverlayCoordinateSpace(faces, thumbnailWidth, thumbnailHeight);

  return faces
    .map((face) => {
      if (
        face.bbox_x === null ||
        face.bbox_y === null ||
        face.bbox_w === null ||
        face.bbox_h === null ||
        face.bbox_w <= 0 ||
        face.bbox_h <= 0
      ) {
        return null;
      }

      const left = clamp((face.bbox_x / coordinateSpace.width) * 100, 0, 100);
      const top = clamp((face.bbox_y / coordinateSpace.height) * 100, 0, 100);
      const right = clamp(((face.bbox_x + face.bbox_w) / coordinateSpace.width) * 100, 0, 100);
      const bottom = clamp(((face.bbox_y + face.bbox_h) / coordinateSpace.height) * 100, 0, 100);
      const width = right - left;
      const height = bottom - top;

      if (width <= 0 || height <= 0) {
        return null;
      }

      return {
        faceId: face.face_id,
        personId: face.person_id,
        labelSource: face.label_source ?? null,
        leftPercent: left,
        topPercent: top,
        widthPercent: width,
        heightPercent: height
      } satisfies FaceOverlayRegion;
    })
    .filter((region): region is FaceOverlayRegion => region !== null);
}

function defaultRegionAriaLabel(region: FaceOverlayRegion, index: number): string {
  return `Face region ${index + 1}${region.personId ? ` for ${region.personId}` : ""}`;
}

export function FaceBBoxOverlay({
  regions,
  ariaLabel,
  getRegionAriaLabel = defaultRegionAriaLabel,
  renderRegionContent,
  onRegionClick
}: FaceBBoxOverlayProps) {
  if (regions.length === 0) {
    return null;
  }

  return (
    <ol className="detail-face-overlay-list" aria-label={ariaLabel}>
      {regions.map((region, index) => (
        <li
          key={region.faceId}
          className={`detail-face-overlay${onRegionClick ? " is-interactive" : ""}`}
          aria-label={getRegionAriaLabel(region, index)}
          role={onRegionClick ? "button" : undefined}
          tabIndex={onRegionClick ? 0 : undefined}
          onClick={onRegionClick ? () => onRegionClick(region, index) : undefined}
          onKeyDown={
            onRegionClick
              ? (event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onRegionClick(region, index);
                  }
                }
              : undefined
          }
          style={{
            left: `${region.leftPercent}%`,
            top: `${region.topPercent}%`,
            width: `${region.widthPercent}%`,
            height: `${region.heightPercent}%`
          }}
        >
          {renderRegionContent ? renderRegionContent(region, index) : null}
        </li>
      ))}
    </ol>
  );
}

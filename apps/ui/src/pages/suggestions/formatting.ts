import type { CSSProperties } from "react";
import type { SuggestionThumbnail } from "./types";

export function formatConfidence(confidence: number): string {
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    return "0.0%";
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

export function formatDisplayPath(path: string): string {
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

export function buildFaceZoomStyle(
  faceRegion: { leftPercent: number; topPercent: number; widthPercent: number; heightPercent: number },
  thumbnail: SuggestionThumbnail
): { frame: CSSProperties; image: CSSProperties } {
  const leftPx = (faceRegion.leftPercent / 100) * thumbnail.width;
  const topPx = (faceRegion.topPercent / 100) * thumbnail.height;
  const widthPx = (faceRegion.widthPercent / 100) * thumbnail.width;
  const heightPx = (faceRegion.heightPercent / 100) * thumbnail.height;
  const padding = 10;
  const cropLeft = Math.max(0, Math.floor(leftPx - padding));
  const cropTop = Math.max(0, Math.floor(topPx - padding));
  const cropRight = Math.min(thumbnail.width, Math.ceil(leftPx + widthPx + padding));
  const cropBottom = Math.min(thumbnail.height, Math.ceil(topPx + heightPx + padding));
  const cropWidth = Math.max(1, cropRight - cropLeft);
  const cropHeight = Math.max(1, cropBottom - cropTop);
  const maxPreviewSize = 170;
  const baseScale = Math.min(maxPreviewSize / cropWidth, maxPreviewSize / cropHeight);
  const scale = Math.max(1.8, Math.min(4.5, baseScale));
  return {
    frame: {
      width: `${Math.round(cropWidth * scale)}px`,
      height: `${Math.round(cropHeight * scale)}px`
    },
    image: {
      width: `${Math.round(thumbnail.width * scale)}px`,
      height: `${Math.round(thumbnail.height * scale)}px`,
      transform: `translate(${-Math.round(cropLeft * scale)}px, ${-Math.round(cropTop * scale)}px)`
    }
  };
}

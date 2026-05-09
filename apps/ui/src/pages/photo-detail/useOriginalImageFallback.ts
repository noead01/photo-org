import { useEffect, useRef, useState } from "react";
import type { PhotoDetailPayload } from "./photoDetailTypes";

function resolveAbsoluteUrl(url: string): string {
  if (typeof window === "undefined") {
    return url;
  }
  return new URL(url, window.location.href).toString();
}

function revokeObjectUrl(url: string): void {
  if (typeof URL.revokeObjectURL === "function") {
    URL.revokeObjectURL(url);
  }
}

function isCurrentImageRequest(image: HTMLImageElement, expectedSrc: string): boolean {
  const expectedAbsoluteSrc = resolveAbsoluteUrl(expectedSrc);
  const currentSrc = image.currentSrc;
  if (currentSrc && currentSrc.length > 0) {
    return currentSrc === expectedAbsoluteSrc;
  }
  const rawSrc = image.getAttribute("src");
  return rawSrc === expectedSrc || rawSrc === expectedAbsoluteSrc;
}

interface UseOriginalImageFallbackResult {
  previewImageSrc: string | null;
  shouldUseOriginalImage: boolean;
  activeOriginalImageSrc: string | null;
  originalImageNaturalSize: { width: number; height: number } | null;
  handleImageLoad: (image: HTMLImageElement) => void;
  handleImageError: (image: HTMLImageElement) => void;
}

export function useOriginalImageFallback(
  photoId: string | undefined,
  detail: PhotoDetailPayload | null
): UseOriginalImageFallbackResult {
  const [isOriginalImageEnabled, setIsOriginalImageEnabled] = useState(true);
  const [originalImageRetrySrc, setOriginalImageRetrySrc] = useState<string | null>(null);
  const [originalImageNaturalSize, setOriginalImageNaturalSize] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const activePhotoIdRef = useRef<string | null>(null);

  useEffect(() => {
    activePhotoIdRef.current = detail?.photo_id ?? null;
  }, [detail?.photo_id]);

  useEffect(() => {
    setIsOriginalImageEnabled(true);
    setOriginalImageNaturalSize(null);
    setOriginalImageRetrySrc((current) => {
      if (current) {
        revokeObjectUrl(current);
      }
      return null;
    });
  }, [photoId]);

  useEffect(() => {
    return () => {
      if (originalImageRetrySrc) {
        revokeObjectUrl(originalImageRetrySrc);
      }
    };
  }, [originalImageRetrySrc]);

  const thumbnailDataUrl = detail?.thumbnail
    ? `data:${detail.thumbnail.mime_type};base64,${detail.thumbnail.data_base64}`
    : null;
  const originalImageUrl = detail ? `/api/v1/photos/${encodeURIComponent(detail.photo_id)}/original` : null;
  const shouldUseOriginalImage = Boolean(originalImageUrl && isOriginalImageEnabled);
  const activeOriginalImageSrc = shouldUseOriginalImage ? (originalImageRetrySrc ?? originalImageUrl) : null;
  const previewImageSrc = activeOriginalImageSrc ?? thumbnailDataUrl;

  async function retryOriginalImageThroughBlob(url: string, expectedPhotoId: string): Promise<boolean> {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (!response.ok) {
        return false;
      }
      const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
      if (!contentType.startsWith("image/")) {
        return false;
      }
      const blob = await response.blob();
      if (blob.size <= 0) {
        return false;
      }
      if (activePhotoIdRef.current !== expectedPhotoId) {
        return false;
      }
      if (typeof URL.createObjectURL !== "function") {
        return false;
      }
      const objectUrl = URL.createObjectURL(blob);
      setOriginalImageRetrySrc((current) => {
        if (current) {
          revokeObjectUrl(current);
        }
        return objectUrl;
      });
      return true;
    } catch {
      return false;
    }
  }

  function handleImageLoad(image: HTMLImageElement) {
    if (
      !shouldUseOriginalImage
      || !activeOriginalImageSrc
      || !isCurrentImageRequest(image, activeOriginalImageSrc)
    ) {
      return;
    }
    const { naturalWidth, naturalHeight } = image;
    if (naturalWidth > 0 && naturalHeight > 0) {
      setOriginalImageNaturalSize({ width: naturalWidth, height: naturalHeight });
    }
  }

  function handleImageError(image: HTMLImageElement) {
    if (
      !shouldUseOriginalImage
      || !activeOriginalImageSrc
      || !isCurrentImageRequest(image, activeOriginalImageSrc)
    ) {
      return;
    }
    if (!originalImageRetrySrc && originalImageUrl && detail) {
      void retryOriginalImageThroughBlob(originalImageUrl, detail.photo_id).then((recovered) => {
        if (recovered) {
          return;
        }
        setIsOriginalImageEnabled(false);
        setOriginalImageNaturalSize(null);
      });
      return;
    }
    setIsOriginalImageEnabled(false);
    setOriginalImageNaturalSize(null);
  }

  return {
    previewImageSrc,
    shouldUseOriginalImage,
    activeOriginalImageSrc,
    originalImageNaturalSize,
    handleImageLoad,
    handleImageError,
  };
}

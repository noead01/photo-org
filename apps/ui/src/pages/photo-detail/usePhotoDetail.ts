import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import { fetchPhotoDetail, PhotoDetailRequestError } from "./photoDetailApi";
import type { PhotoDetailPayload } from "./photoDetailTypes";

interface UsePhotoDetailState {
  detail: PhotoDetailPayload | null;
  isLoading: boolean;
  error: string | null;
  isNotFound: boolean;
  retry: () => void;
  setDetail: Dispatch<SetStateAction<PhotoDetailPayload | null>>;
}

export function usePhotoDetail(photoId: string | undefined): UsePhotoDetailState {
  const [detail, setDetail] = useState<PhotoDetailPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!photoId) {
      setError("Photo identifier is missing.");
      setIsNotFound(false);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    setIsNotFound(false);

    fetchPhotoDetail(photoId)
      .then((payload) => {
        if (controller.signal.aborted) {
          return;
        }
        setIsNotFound(false);
        setDetail(payload);
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        if (caughtError instanceof PhotoDetailRequestError && caughtError.status === 404) {
          setDetail(null);
          setError(null);
          setIsNotFound(true);
          setIsLoading(false);
          return;
        }

        setError(caughtError instanceof Error ? caughtError.message : "Could not load photo detail.");
        setIsNotFound(false);
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [photoId, reloadToken]);

  function retry() {
    setReloadToken((current) => current + 1);
  }

  return {
    detail,
    isLoading,
    error,
    isNotFound,
    retry,
    setDetail,
  };
}

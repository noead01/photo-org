import { useEffect, type MutableRefObject, type RefObject } from "react";
import type { LibraryPhoto } from "./libraryRouteTypes";

interface UseLibraryReturnFocusArgs {
  headingRef: RefObject<HTMLHeadingElement>;
  pendingReturnFocusPhotoIdRef: MutableRefObject<string | null>;
  isLoading: boolean;
  error: string | null;
  photos: LibraryPhoto[];
}

export function useLibraryReturnFocus({
  headingRef,
  pendingReturnFocusPhotoIdRef,
  isLoading,
  error,
  photos,
}: UseLibraryReturnFocusArgs) {
  useEffect(() => {
    const pendingPhotoId = pendingReturnFocusPhotoIdRef.current;
    if (!pendingPhotoId || isLoading) {
      return;
    }

    const timer = window.setTimeout(() => {
      if (error) {
        headingRef.current?.focus();
        pendingReturnFocusPhotoIdRef.current = null;
        return;
      }

      const focusTarget = document.querySelector<HTMLAnchorElement>(
        `[data-photo-id="${pendingPhotoId}"]`
      );

      if (focusTarget) {
        focusTarget.focus();
      } else {
        headingRef.current?.focus();
      }

      pendingReturnFocusPhotoIdRef.current = null;
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [error, headingRef, isLoading, pendingReturnFocusPhotoIdRef, photos]);
}

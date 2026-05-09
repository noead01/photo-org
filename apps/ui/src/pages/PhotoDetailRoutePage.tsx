import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { deriveIngestStatus } from "../app/ingestStatus";
import { buildFaceOverlayRegions, type FaceOverlayRegion } from "./FaceBBoxOverlay";
import { PhotoFaceAssignmentModal } from "./PhotoFaceAssignmentModal";
import { applyFaceAssignment, applyFaceDismissal } from "./face-labeling/faceLabelingState";
import { resolveDetailReturnState, setPendingLibraryFocusPhotoId } from "./libraryRouteState";
import { sortPeopleDirectory } from "./people/peopleState";
import { PhotoMetadataFlyout } from "./photo-interactions/PhotoMetadataFlyout";
import { fetchPeopleDirectory } from "./photo-detail/photoDetailApi";
import { MISSING_VALUE } from "./photo-detail/photoDetailFormatting";
import { PhotoPreviewPanel } from "./photo-detail/PhotoPreviewPanel";
import type { PersonRecord, PhotoDetailPayload } from "./photo-detail/photoDetailTypes";
import { useOriginalImageFallback } from "./photo-detail/useOriginalImageFallback";
import { usePhotoDetail } from "./photo-detail/usePhotoDetail";

function derivePersonInitials(displayName: string | null): string {
  if (!displayName) {
    return "?";
  }
  const tokens = displayName
    .trim()
    .split(/\s+/)
    .map((token) => token.replace(/[^a-zA-Z0-9]/g, ""))
    .filter((token) => token.length > 0);
  if (tokens.length === 0) {
    return "?";
  }
  if (tokens.length === 1) {
    const [token] = tokens;
    return token.slice(0, Math.min(2, token.length)).toUpperCase();
  }
  return `${tokens[0][0] ?? ""}${tokens[1][0] ?? ""}`.toUpperCase();
}

function syncPeopleFromFaces(detail: PhotoDetailPayload): PhotoDetailPayload {
  const nextPeople = Array.from(
    new Set(
      detail.faces
        .map((face) => face.person_id)
        .filter((value): value is string => value !== null)
    )
  );
  return {
    ...detail,
    people: nextPeople,
  };
}

export function PhotoDetailRoutePage() {
  const location = useLocation();
  const { photoId } = useParams<{ photoId: string }>();
  const returnState = resolveDetailReturnState(location.state);
  const headingRef = useRef<HTMLHeadingElement | null>(null);
  const { detail, setDetail, isLoading, error, isNotFound, retry } = usePhotoDetail(photoId);
  const [imageScalePercent, setImageScalePercent] = useState(100);
  const [showFaceBoxes, setShowFaceBoxes] = useState(true);
  const [isDetailFlyoutOpen, setIsDetailFlyoutOpen] = useState(false);
  const [activeFaceModalId, setActiveFaceModalId] = useState<string | null>(null);
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);

  const {
    previewImageSrc,
    shouldUseOriginalImage,
    activeOriginalImageSrc,
    originalImageNaturalSize,
    handleImageLoad,
    handleImageError,
  } = useOriginalImageFallback(photoId, detail);

  useEffect(() => {
    headingRef.current?.focus();
  }, [photoId]);

  useEffect(() => {
    setIsDetailFlyoutOpen(false);
  }, [photoId]);

  useEffect(() => {
    const controller = new AbortController();

    fetchPeopleDirectory(controller.signal)
      .then((payload) => {
        setPeopleDirectory(sortPeopleDirectory(payload));
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setPeopleDirectory([]);
        }
      });

    return () => {
      controller.abort();
    };
  }, [photoId]);

  const faceOverlayRegions = useMemo<FaceOverlayRegion[]>(() => {
    if (!detail?.thumbnail || detail.thumbnail.width <= 0 || detail.thumbnail.height <= 0) {
      return [];
    }

    return buildFaceOverlayRegions(detail.faces, detail.thumbnail.width, detail.thumbnail.height);
  }, [detail]);

  const faceRegionState = useMemo(() => {
    if (!detail) {
      return MISSING_VALUE;
    }

    if (detail.faces.length === 0) {
      return "No face regions detected for this photo.";
    }

    if (!showFaceBoxes) {
      return "Face boxes are hidden for this preview.";
    }

    if (faceOverlayRegions.length === 0) {
      return "Face regions are present but could not be rendered on this preview.";
    }

    return `${faceOverlayRegions.length} face region${faceOverlayRegions.length === 1 ? "" : "s"} rendered.`;
  }, [detail, faceOverlayRegions.length, showFaceBoxes]);

  const ingestStatus = useMemo(() => {
    if (!detail) {
      return null;
    }
    return deriveIngestStatus({
      availabilityState: detail.original?.availability_state ?? null,
      isAvailable: detail.original?.is_available ?? null,
      lastFailureReason: detail.original?.last_failure_reason ?? null,
      hasThumbnail: Boolean(detail.thumbnail),
      includeFaceDetection: true,
      facesDetectedTs: detail.metadata.faces_detected_ts,
    });
  }, [detail]);

  const peopleNameById = useMemo(() => {
    return new Map(peopleDirectory.map((person) => [person.person_id, person.display_name]));
  }, [peopleDirectory]);

  const faceBadgeInitialsById = useMemo(() => {
    return new Map(
      (detail?.faces ?? []).map((face) => [
        face.face_id,
        face.person_id ? derivePersonInitials(peopleNameById.get(face.person_id) ?? null) : "?",
      ])
    );
  }, [detail?.faces, peopleNameById]);

  const selectedFaceForModal = useMemo(() => {
    if (!detail || !activeFaceModalId) {
      return null;
    }
    const index = detail.faces.findIndex((face) => face.face_id === activeFaceModalId);
    if (index < 0) {
      return null;
    }
    return { ...detail.faces[index], sequence: index + 1 };
  }, [activeFaceModalId, detail]);

  const selectedRegionForModal = useMemo(() => {
    if (!activeFaceModalId) {
      return null;
    }
    return faceOverlayRegions.find((region) => region.faceId === activeFaceModalId) ?? null;
  }, [activeFaceModalId, faceOverlayRegions]);

  const backLinkFocusPhotoId = detail?.photo_id ?? returnState.returnFocusPhotoId ?? photoId ?? null;

  function handleFaceAssigned(faceId: string, personId: string) {
    setDetail((current) => {
      if (!current) {
        return current;
      }
      const next = applyFaceAssignment(current, faceId, personId);
      return syncPeopleFromFaces(next);
    });
  }

  function handleFaceDismissed(faceId: string) {
    setDetail((current) => {
      if (!current) {
        return current;
      }
      const next = applyFaceDismissal(current, faceId);
      return syncPeopleFromFaces({
        ...next,
        metadata: {
          ...next.metadata,
          faces_count: next.faces.length,
        },
      });
    });
    setActiveFaceModalId((current) => (current === faceId ? null : current));
  }

  function handlePersonCreated(person: {
    person_id: string;
    display_name: string;
    created_ts?: string;
    updated_ts?: string;
  }) {
    setPeopleDirectory((current) => {
      if (current.some((candidate) => candidate.person_id === person.person_id)) {
        return current;
      }
      return sortPeopleDirectory([
        ...current,
        {
          person_id: person.person_id,
          display_name: person.display_name,
          created_ts: person.created_ts ?? new Date().toISOString(),
          updated_ts: person.updated_ts ?? new Date().toISOString(),
        },
      ]);
    });
  }

  return (
    <section aria-labelledby="page-title" className="page detail-page">
      <div className="detail-header">
        <div>
          <h1 id="page-title" ref={headingRef} tabIndex={-1}>
            Photo detail
          </h1>
          <p>Inspect canonical metadata and availability fields for a single photo.</p>
        </div>
        <Link
          className="detail-back-link"
          to={{
            pathname: "/library",
            search: returnState.returnToLibrarySearch ?? "",
          }}
          state={
            backLinkFocusPhotoId || returnState.librarySelection || returnState.libraryViewState
              ? {
                  restoreFocusPhotoId: backLinkFocusPhotoId ?? undefined,
                  librarySelection: returnState.librarySelection,
                  libraryViewState: returnState.libraryViewState,
                }
              : undefined
          }
          onClick={() => {
            if (backLinkFocusPhotoId) {
              setPendingLibraryFocusPhotoId(backLinkFocusPhotoId);
            }
          }}
        >
          Back to library
        </Link>
      </div>
      {isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading photo detail.
        </div>
      ) : null}

      {!isLoading && error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load photo detail</h2>
          <p>{error}</p>
          <button type="button" onClick={retry}>
            Retry
          </button>
        </div>
      ) : null}

      {!isLoading && !error && detail ? (
        <div className="detail-workspace">
          <PhotoPreviewPanel
            detailPhotoId={detail.photo_id}
            previewImageSrc={previewImageSrc}
            shouldUseOriginalImage={shouldUseOriginalImage}
            activeOriginalImageSrc={activeOriginalImageSrc}
            thumbnailSize={
              !shouldUseOriginalImage && detail.thumbnail
                ? { width: detail.thumbnail.width, height: detail.thumbnail.height }
                : originalImageNaturalSize
            }
            ingestStatus={ingestStatus}
            showFaceBoxes={showFaceBoxes}
            imageScalePercent={imageScalePercent}
            faceOverlayRegions={faceOverlayRegions}
            faceBadgeInitialsById={faceBadgeInitialsById}
            faceRegionState={faceRegionState}
            onShowFaceBoxesChange={setShowFaceBoxes}
            onImageScalePercentChange={setImageScalePercent}
            onToggleDetails={() => setIsDetailFlyoutOpen((current) => !current)}
            isDetailFlyoutOpen={isDetailFlyoutOpen}
            onOpenFaceAssignment={(faceId) => setActiveFaceModalId(faceId)}
            onImageLoad={handleImageLoad}
            onImageError={handleImageError}
          />

          <PhotoMetadataFlyout
            key={`detail-metadata-${detail.photo_id}`}
            summary={{
              photoId: detail.photo_id,
              title: detail.photo_id,
              path: detail.path,
              thumbnail: detail.thumbnail
                ? {
                    mimeType: detail.thumbnail.mime_type,
                    width: detail.thumbnail.width,
                    height: detail.thumbnail.height,
                    dataBase64: detail.thumbnail.data_base64
                  }
                : null
            }}
            detail={detail}
            ingestStatus={ingestStatus}
            isOpen={isDetailFlyoutOpen}
            isLoadingDetail={false}
            detailError={null}
            onClose={() => setIsDetailFlyoutOpen(false)}
            onRetry={retry}
          />
        </div>
      ) : null}

      {!isLoading && !error && isNotFound ? (
        <section className="feedback-panel" aria-labelledby="photo-not-found-title">
          <h2 id="photo-not-found-title">Photo not found</h2>
          <p>This photo is no longer available in the catalog.</p>
        </section>
      ) : null}

      <PhotoFaceAssignmentModal
        isOpen={selectedFaceForModal !== null}
        face={selectedFaceForModal}
        region={selectedRegionForModal}
        thumbnail={detail?.thumbnail ?? null}
        people={peopleDirectory.map((person) => ({
          person_id: person.person_id,
          display_name: person.display_name,
          created_ts: person.created_ts,
          updated_ts: person.updated_ts,
        }))}
        onClose={() => setActiveFaceModalId(null)}
        onFaceUpdated={handleFaceAssigned}
        onFaceDismissed={handleFaceDismissed}
        onPersonCreated={handlePersonCreated}
      />
    </section>
  );
}

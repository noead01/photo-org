import { useMemo, useState } from "react";
import { FaceAssignmentControls } from "../FaceAssignmentControls";
import type { FaceAssignmentFace, FaceAssignmentPerson } from "../FaceAssignmentControls";
import type { LibraryPhoto } from "./libraryRouteTypes";

type FaceLabelSource = "human_confirmed" | "machine_applied" | "machine_suggested" | null;

type FaceRegion = FaceAssignmentFace & {
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
};

type PhotoDetailPayload = {
  photo_id: string;
  faces: FaceRegion[];
  thumbnail: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
};

type FaceOverlayRegion = {
  faceId: string;
  personId: string | null;
  labelSource: FaceLabelSource;
  leftPercent: number;
  topPercent: number;
  widthPercent: number;
  heightPercent: number;
};

type FaceBBox = {
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function inferFaceOverlayCoordinateSpace(
  faces: FaceBBox[],
  thumbnailWidth: number,
  thumbnailHeight: number
): { width: number; height: number } {
  // Face coordinates are stored in source-image pixels; use detected extents when thumbnail space is smaller.
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

function provenanceBadgeIcon(source: FaceLabelSource): string {
  if (source === "human_confirmed") {
    return "👤";
  }
  if (source === "machine_applied") {
    return "🤖";
  }
  if (source === "machine_suggested") {
    return "💡";
  }
  return "❓";
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Ignore parse errors and use fallback mapping.
  }

  return null;
}

function applyFaceAssignment(
  payload: PhotoDetailPayload,
  faceId: string,
  personId: string
): PhotoDetailPayload {
  return {
    ...payload,
    faces: payload.faces.map((face) =>
      face.face_id === faceId
        ? {
            ...face,
            person_id: personId,
            label_source: null,
            confidence: null,
            model_version: null,
            provenance: null,
            label_recorded_ts: null
          }
        : face
    )
  };
}

function mapConfirmationError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to confirm face assignments.";
  }

  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }

  if (status === 409) {
    return detail ?? "Face confirmation could not be applied.";
  }

  return `Confirmation request failed (${status}).`;
}

function resolvePersonLabel(people: FaceAssignmentPerson[], personId: string): string {
  const match = people.find((person) => person.person_id === personId);
  return match ? match.display_name : personId;
}

function buildOverlayRegions(payload: PhotoDetailPayload | null): FaceOverlayRegion[] {
  if (!payload?.thumbnail || payload.thumbnail.width <= 0 || payload.thumbnail.height <= 0) {
    return [];
  }

  const thumbnailWidth = payload.thumbnail.width;
  const thumbnailHeight = payload.thumbnail.height;
  const coordinateSpace = inferFaceOverlayCoordinateSpace(payload.faces, thumbnailWidth, thumbnailHeight);

  return payload.faces
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
      };
    })
    .filter((region): region is FaceOverlayRegion => region !== null);
}

async function fetchPhotoDetail(photoId: string): Promise<PhotoDetailPayload> {
  const response = await fetch(`/api/v1/photos/${photoId}`);
  if (!response.ok) {
    throw new Error(`Photo detail request failed (${response.status})`);
  }
  return (await response.json()) as PhotoDetailPayload;
}

async function fetchPeopleDirectory(): Promise<FaceAssignmentPerson[]> {
  const response = await fetch("/api/v1/people");
  if (!response.ok) {
    throw new Error(`People request failed (${response.status})`);
  }
  return (await response.json()) as FaceAssignmentPerson[];
}

interface LibraryPhotoFacePanelProps {
  photo: LibraryPhoto;
}

export function LibraryPhotoFacePanel({ photo }: LibraryPhotoFacePanelProps) {
  const hasDetectedFaces = (photo.faces?.length ?? 0) > 0;
  const panelId = `library-face-panel-${photo.photo_id}`;
  const [isExpanded, setIsExpanded] = useState(false);
  const [detail, setDetail] = useState<PhotoDetailPayload | null>(null);
  const [people, setPeople] = useState<FaceAssignmentPerson[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [requestedExpandedProvenanceFaceId, setRequestedExpandedProvenanceFaceId] = useState<
    string | null
  >(null);
  const [confirmFaceIdInFlight, setConfirmFaceIdInFlight] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [confirmMessage, setConfirmMessage] = useState<string | null>(null);

  const overlayRegions = useMemo(() => buildOverlayRegions(detail), [detail]);

  const machineLabeledFaces = useMemo(() => {
    if (!detail) {
      return [] as Array<FaceRegion & { sequence: number; person_id: string }>;
    }

    return detail.faces
      .map((face, index) => ({ ...face, sequence: index + 1 }))
      .filter(
        (face): face is FaceRegion & { sequence: number; person_id: string } =>
          face.person_id !== null &&
          (face.label_source === "machine_applied" || face.label_source === "machine_suggested")
      );
  }, [detail]);

  const faceRegionState = useMemo(() => {
    if (!detail) {
      return "Face regions unavailable.";
    }

    if (detail.faces.length === 0) {
      return "No face regions detected for this photo.";
    }

    if (overlayRegions.length === 0) {
      return "Face regions are present but could not be rendered on this preview.";
    }

    return `${overlayRegions.length} face region${overlayRegions.length === 1 ? "" : "s"} rendered.`;
  }, [detail, overlayRegions.length]);

  async function loadPanelData() {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [detailPayload, peoplePayload] = await Promise.all([
        fetchPhotoDetail(photo.photo_id),
        fetchPeopleDirectory()
      ]);
      setDetail(detailPayload);
      setPeople(peoplePayload);
    } catch (caughtError: unknown) {
      setLoadError(caughtError instanceof Error ? caughtError.message : "Could not load face workflow.");
    } finally {
      setIsLoading(false);
    }
  }

  async function confirmFace(faceId: string, personId: string, sequence: number) {
    setConfirmFaceIdInFlight(faceId);
    setConfirmError(null);
    setConfirmMessage(null);

    try {
      const response = await fetch(`/api/v1/faces/${faceId}/confirmations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ person_id: personId })
      });

      if (!response.ok) {
        const detailMessage = await readErrorDetail(response);
        setConfirmError(mapConfirmationError(response.status, detailMessage));
        return;
      }

      setDetail((current) =>
        current
          ? {
              ...current,
              faces: current.faces.map((face) =>
                face.face_id === faceId
                  ? {
                      ...face,
                      label_source: "human_confirmed",
                      provenance: face.provenance ?? {
                        action: "confirmation",
                        surface: "library-quick-panel",
                        workflow: "face-labeling"
                      },
                      label_recorded_ts: face.label_recorded_ts ?? new Date().toISOString()
                    }
                  : face
              )
            }
          : current
      );
      setConfirmMessage(
        `Confirmed face ${sequence} for ${resolvePersonLabel(people, personId)}.`
      );
    } catch {
      setConfirmError("Could not confirm face assignment.");
    } finally {
      setConfirmFaceIdInFlight(null);
    }
  }

  if (!hasDetectedFaces) {
    return null;
  }

  return (
    <section className="library-face-panel">
      <button
        type="button"
        className="library-face-panel-toggle"
        aria-expanded={isExpanded}
        aria-controls={panelId}
        onClick={() => {
          const nextExpanded = !isExpanded;
          setIsExpanded(nextExpanded);
          if (nextExpanded && detail === null && !isLoading) {
            void loadPanelData();
          }
        }}
      >
        {isExpanded ? "Hide face review" : "Review faces"}
      </button>

      {isExpanded ? (
        <div id={panelId} className="library-face-panel-body">
          {isLoading ? (
            <p className="library-face-panel-status" role="status">
              Loading face workflow…
            </p>
          ) : null}
          {!isLoading && loadError ? (
            <div className="library-face-panel-error">
              <p>{loadError}</p>
              <button
                type="button"
                onClick={() => {
                  void loadPanelData();
                }}
              >
                Retry
              </button>
            </div>
          ) : null}

          {!isLoading && !loadError && detail ? (
            <div className="library-face-panel-content">
              {detail.thumbnail ? (
                <div className="detail-media-frame" data-mode="fit">
                  <div className="detail-media-stage">
                    <img
                      className="detail-media-image"
                      src={`data:${detail.thumbnail.mime_type};base64,${detail.thumbnail.data_base64}`}
                      width={detail.thumbnail.width}
                      height={detail.thumbnail.height}
                      alt={`Preview for ${detail.photo_id}`}
                    />
                    {overlayRegions.length > 0 ? (
                      <ol className="detail-face-overlay-list" aria-label="Detected face regions">
                        {overlayRegions.map((region, index) => (
                          <li
                            key={region.faceId}
                            className="detail-face-overlay"
                            aria-label={`Face region ${index + 1}${region.personId ? ` for ${region.personId}` : ""}`}
                            style={{
                              left: `${region.leftPercent}%`,
                              top: `${region.topPercent}%`,
                              width: `${region.widthPercent}%`,
                              height: `${region.heightPercent}%`
                            }}
                          >
                            <button
                              type="button"
                              className="detail-face-overlay-provenance-button"
                              aria-label={`Show provenance details for face region ${index + 1}`}
                              onClick={() => {
                                setRequestedExpandedProvenanceFaceId(region.faceId);
                              }}
                            >
                              {provenanceBadgeIcon(region.labelSource)}
                            </button>
                          </li>
                        ))}
                      </ol>
                    ) : null}
                  </div>
                </div>
              ) : (
                <div className="browse-thumbnail browse-thumbnail-placeholder" aria-hidden="true">
                  No preview
                </div>
              )}

              <p className="detail-face-state">{faceRegionState}</p>

              {machineLabeledFaces.length > 0 ? (
                <section className="library-face-confirmation" aria-label="Face confirmation">
                  <h3>Confirm machine labels</h3>
                  <ul>
                    {machineLabeledFaces.map((face) => (
                      <li key={face.face_id}>
                        <span>
                          Face {face.sequence}: {resolvePersonLabel(people, face.person_id)}
                        </span>
                        <button
                          type="button"
                          disabled={confirmFaceIdInFlight !== null}
                          onClick={() => {
                            void confirmFace(face.face_id, face.person_id, face.sequence);
                          }}
                        >
                          Confirm label
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {confirmMessage ? (
                <p className="library-face-confirmation-success">{confirmMessage}</p>
              ) : null}
              {confirmError ? <p className="detail-face-assignment-error">{confirmError}</p> : null}

              <FaceAssignmentControls
                faces={detail.faces}
                people={people}
                onAssigned={(faceId, personId) =>
                  setDetail((current) => (current ? applyFaceAssignment(current, faceId, personId) : current))
                }
                onCorrected={(faceId, personId) =>
                  setDetail((current) => (current ? applyFaceAssignment(current, faceId, personId) : current))
                }
                requestedExpandedProvenanceFaceId={requestedExpandedProvenanceFaceId}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

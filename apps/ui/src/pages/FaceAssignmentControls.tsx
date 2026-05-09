import { useEffect, useMemo, useState } from "react";
import {
  FaceLabelingApiError,
  assignFace,
  correctFace,
  markFaceUnknown,
} from "./face-labeling/faceLabelingApi";

type FaceLabelSource = "human_confirmed" | "machine_suggested" | null;

const NOT_AVAILABLE = "Not available";
const UNKNOWN_PERSON_OPTION_VALUE = "__unknown_person__";

export interface FaceAssignmentFace {
  face_id: string;
  person_id: string | null;
  label_source?: FaceLabelSource;
  confidence?: number | null;
  model_version?: string | null;
  provenance?: Record<string, unknown> | null;
  label_recorded_ts?: string | null;
}

export interface FaceAssignmentPerson {
  person_id: string;
  display_name: string;
}

interface FaceAssignmentControlsProps {
  faces: FaceAssignmentFace[];
  people: FaceAssignmentPerson[];
  onAssigned: (faceId: string, personId: string) => void;
  onCorrected: (faceId: string, personId: string) => void;
  requestedExpandedProvenanceFaceId?: string | null;
}

function resolvePersonLabel(people: FaceAssignmentPerson[], personId: string): string {
  const match = people.find((person) => person.person_id === personId);
  return match ? match.display_name : personId;
}

function provenanceBadgeIcon(source: FaceLabelSource | undefined): string {
  if (source === "human_confirmed") {
    return "👤";
  }
  if (source === "machine_suggested") {
    return "💡";
  }
  return "❓";
}

function provenanceSourceLabel(source: FaceLabelSource | undefined): string {
  if (source === "human_confirmed") {
    return "Human confirmed";
  }
  if (source === "machine_suggested") {
    return "Machine suggested";
  }
  return "Unknown";
}

function readProvenanceValue(face: FaceAssignmentFace, key: string): string {
  if (!face.provenance || typeof face.provenance !== "object") {
    return NOT_AVAILABLE;
  }
  const value = face.provenance[key];
  if (typeof value === "string" && value.trim().length > 0) {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return NOT_AVAILABLE;
}

function formatConfidence(confidence: number | null | undefined): string {
  if (typeof confidence !== "number" || !Number.isFinite(confidence)) {
    return NOT_AVAILABLE;
  }
  if (confidence < 0 || confidence > 1) {
    return NOT_AVAILABLE;
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

function formatRecordedTimestamp(value: string | null | undefined): string {
  if (!value || value.trim().length === 0) {
    return NOT_AVAILABLE;
  }
  return value;
}

export function FaceAssignmentControls({
  faces,
  people,
  onAssigned,
  onCorrected,
  requestedExpandedProvenanceFaceId = null
}: FaceAssignmentControlsProps) {
  const indexedFaces = useMemo(
    () => faces.map((face, index) => ({ ...face, sequence: index + 1 })),
    [faces]
  );
  const unlabeledFaces = useMemo(
    () => indexedFaces.filter((face) => face.person_id === null),
    [indexedFaces]
  );
  const labeledFaces = useMemo(
    () =>
      indexedFaces.filter(
        (face): face is FaceAssignmentFace & { sequence: number; person_id: string } =>
          face.person_id !== null
      ),
    [indexedFaces]
  );
  const [activeIndex, setActiveIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [assignmentError, setAssignmentError] = useState<string | null>(null);
  const [correctionSelections, setCorrectionSelections] = useState<Record<string, string>>({});
  const [correctionFaceIdInFlight, setCorrectionFaceIdInFlight] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [correctionProvenance, setCorrectionProvenance] = useState<string | null>(null);
  const [expandedProvenanceFaceId, setExpandedProvenanceFaceId] = useState<string | null>(null);

  const activeFace = unlabeledFaces[activeIndex] ?? null;
  const isBusy = isSubmitting || correctionFaceIdInFlight !== null;

  useEffect(() => {
    if (!requestedExpandedProvenanceFaceId) {
      return;
    }
    const isKnownLabeledFace = labeledFaces.some(
      (face) => face.face_id === requestedExpandedProvenanceFaceId
    );
    if (isKnownLabeledFace) {
      setExpandedProvenanceFaceId(requestedExpandedProvenanceFaceId);
    }
  }, [requestedExpandedProvenanceFaceId, labeledFaces]);

  async function assign(faceId: string, personId: string) {
    setIsSubmitting(true);
    setAssignmentError(null);
    setCorrectionProvenance(null);

    try {
      const payload = await assignFace(faceId, personId);
      onAssigned(faceId, payload.person_id ?? personId);
      setActiveIndex((current) => current + 1);
    } catch (caughtError: unknown) {
      setAssignmentError(
        caughtError instanceof FaceLabelingApiError && caughtError.message.trim().length > 0
          ? caughtError.message
          : "Could not assign face."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function assignUnknown(faceId: string) {
    setIsSubmitting(true);
    setAssignmentError(null);
    setCorrectionProvenance(null);

    try {
      const payload = await markFaceUnknown(faceId);
      onAssigned(faceId, payload.person_id);
      setActiveIndex((current) => current + 1);
    } catch (caughtError: unknown) {
      setAssignmentError(
        caughtError instanceof FaceLabelingApiError && caughtError.message.trim().length > 0
          ? caughtError.message
          : "Could not assign face."
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  async function correct(faceId: string, previousPersonId: string, personId: string) {
    setCorrectionFaceIdInFlight(faceId);
    setCorrectionError(null);
    setAssignmentError(null);
    setCorrectionProvenance(null);

    try {
      const payload = await correctFace(faceId, personId);
      const previousId = payload.previous_person_id ?? previousPersonId;
      const nextId = payload.person_id ?? personId;
      onCorrected(faceId, nextId);
      setCorrectionSelections((current) => {
        const { [faceId]: _discard, ...rest } = current;
        return rest;
      });
      setCorrectionProvenance(
        `Correction recorded: ${resolvePersonLabel(people, previousId)} -> ${resolvePersonLabel(people, nextId)}.`
      );
    } catch (caughtError: unknown) {
      setCorrectionError(
        caughtError instanceof FaceLabelingApiError && caughtError.message.trim().length > 0
          ? caughtError.message
          : "Could not correct face assignment."
      );
    } finally {
      setCorrectionFaceIdInFlight(null);
    }
  }

  return (
    <>
      <section className="detail-face-assignment" aria-label="Face assignment">
        <h3>Assign detected faces</h3>
        {activeFace === null ? (
          <p className="detail-face-assignment-complete">All visible faces assigned.</p>
        ) : (
          <>
            <label htmlFor={`assign-${activeFace.face_id}`}>{`Assign face ${activeIndex + 1}`}</label>
            <select
              id={`assign-${activeFace.face_id}`}
              aria-label={`Assign face ${activeIndex + 1}`}
              disabled={isBusy}
              value=""
              onChange={(event) => {
                const personId = event.target.value;
                if (!personId) {
                  return;
                }
                if (personId === UNKNOWN_PERSON_OPTION_VALUE) {
                  void assignUnknown(activeFace.face_id);
                  return;
                }
                void assign(activeFace.face_id, personId);
              }}
            >
              <option value="" disabled>
                Select person
              </option>
              <option value={UNKNOWN_PERSON_OPTION_VALUE}>Human face (name unknown)</option>
              {people.map((person) => (
                <option key={person.person_id} value={person.person_id}>
                  {person.display_name}
                </option>
              ))}
            </select>
          </>
        )}
        {assignmentError ? <p className="detail-face-assignment-error">{assignmentError}</p> : null}
      </section>

      {labeledFaces.length > 0 ? (
        <section className="detail-face-correction" aria-label="Face correction">
          <h3>Correct labeled faces</h3>
          <ul>
            {labeledFaces.map((face) => {
              const selectedPersonId = correctionSelections[face.face_id] ?? "";
              const isProvenanceExpanded = expandedProvenanceFaceId === face.face_id;
              return (
                <li key={face.face_id}>
                  <div className="detail-face-correction-row">
                    <p>{`Face ${face.sequence}: ${resolvePersonLabel(people, face.person_id)}`}</p>
                    <button
                      type="button"
                      className="detail-face-provenance-badge"
                      aria-label={`Show provenance details for face ${face.sequence}`}
                      aria-expanded={isProvenanceExpanded}
                      onClick={() => {
                        setExpandedProvenanceFaceId((current) =>
                          current === face.face_id ? null : face.face_id
                        );
                      }}
                    >
                      {provenanceBadgeIcon(face.label_source)}
                    </button>
                  </div>
                  <div className="detail-face-correction-controls">
                    <select
                      id={`correct-${face.face_id}`}
                      aria-label={`Correct face ${face.sequence}`}
                      disabled={isBusy}
                      value={selectedPersonId}
                      onChange={(event) => {
                        const personId = event.target.value;
                        setCorrectionSelections((current) => ({
                          ...current,
                          [face.face_id]: personId
                        }));
                      }}
                    >
                      <option value="">Select replacement person</option>
                      {people
                        .filter((person) => person.person_id !== face.person_id)
                        .map((person) => (
                          <option key={person.person_id} value={person.person_id}>
                            {person.display_name}
                          </option>
                        ))}
                    </select>
                    <button
                      type="button"
                      disabled={isBusy || selectedPersonId.length === 0}
                      onClick={() => {
                        if (!selectedPersonId) {
                          return;
                        }
                        void correct(face.face_id, face.person_id, selectedPersonId);
                      }}
                    >
                      Confirm reassignment
                    </button>
                  </div>
                  {isProvenanceExpanded ? (
                    <dl
                      className="detail-face-provenance-details"
                      aria-label={`Provenance details for face ${face.sequence}`}
                    >
                      <div>
                        <dt>Source</dt>
                        <dd>{provenanceSourceLabel(face.label_source)}</dd>
                      </div>
                      <div>
                        <dt>Action</dt>
                        <dd>{readProvenanceValue(face, "action")}</dd>
                      </div>
                      <div>
                        <dt>Surface</dt>
                        <dd>{readProvenanceValue(face, "surface")}</dd>
                      </div>
                      <div>
                        <dt>Workflow</dt>
                        <dd>{readProvenanceValue(face, "workflow")}</dd>
                      </div>
                      <div>
                        <dt>Model version</dt>
                        <dd>{face.model_version ?? NOT_AVAILABLE}</dd>
                      </div>
                      <div>
                        <dt>Confidence</dt>
                        <dd>{formatConfidence(face.confidence)}</dd>
                      </div>
                      <div>
                        <dt>Recorded</dt>
                        <dd>{formatRecordedTimestamp(face.label_recorded_ts)}</dd>
                      </div>
                    </dl>
                  ) : null}
                </li>
              );
            })}
          </ul>
          {correctionProvenance ? (
            <p className="detail-face-correction-provenance">{correctionProvenance}</p>
          ) : null}
          {correctionError ? <p className="detail-face-assignment-error">{correctionError}</p> : null}
        </section>
      ) : null}
    </>
  );
}

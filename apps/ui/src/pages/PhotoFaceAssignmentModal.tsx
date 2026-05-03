import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type { FaceOverlayRegion } from "./FaceBBoxOverlay";

interface FaceAssignmentModalFace {
  face_id: string;
  person_id: string | null;
}

interface FaceAssignmentModalPerson {
  person_id: string;
  display_name: string;
  created_ts?: string;
  updated_ts?: string;
}

interface FaceThumbnail {
  mime_type: string;
  width: number;
  height: number;
  data_base64: string;
}

interface FaceCandidate {
  person_id: string;
  display_name: string;
  confidence: number;
}

interface FaceCandidateLookupPayload {
  candidates?: FaceCandidate[];
}

interface PhotoFaceAssignmentModalProps {
  isOpen: boolean;
  face: (FaceAssignmentModalFace & { sequence: number }) | null;
  region: FaceOverlayRegion | null;
  thumbnail: FaceThumbnail | null;
  people: FaceAssignmentModalPerson[];
  onClose: () => void;
  onFaceUpdated: (faceId: string, personId: string) => void;
  onPersonCreated: (person: FaceAssignmentModalPerson) => void;
}

function normalizeName(value: string): string {
  return value.trim().toLowerCase();
}

function resolvePersonName(people: FaceAssignmentModalPerson[], personId: string | null): string {
  if (!personId) {
    return "Unassigned";
  }
  const match = people.find((person) => person.person_id === personId);
  return match ? match.display_name : personId;
}

function formatConfidence(confidence: number): string {
  if (!Number.isFinite(confidence) || confidence < 0 || confidence > 1) {
    return "0.0%";
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

function mapAssignmentError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to assign faces.";
  }
  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face is already assigned.";
  }
  return `Assignment request failed (${status}).`;
}

function mapCorrectionError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to correct face assignments.";
  }
  if (status === 404) {
    return detail ?? "Face or person no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face correction could not be applied.";
  }
  return `Correction request failed (${status}).`;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall through to default message.
  }
  return null;
}

function buildCropStyle(region: FaceOverlayRegion | null, thumbnail: FaceThumbnail | null): {
  frame: CSSProperties;
  image: CSSProperties;
} | null {
  if (!region || !thumbnail || thumbnail.width <= 0 || thumbnail.height <= 0) {
    return null;
  }

  const leftPx = (region.leftPercent / 100) * thumbnail.width;
  const topPx = (region.topPercent / 100) * thumbnail.height;
  const widthPx = (region.widthPercent / 100) * thumbnail.width;
  const heightPx = (region.heightPercent / 100) * thumbnail.height;

  if (widthPx <= 0 || heightPx <= 0) {
    return null;
  }

  const padding = 8;
  const cropLeft = Math.max(0, Math.floor(leftPx - padding));
  const cropTop = Math.max(0, Math.floor(topPx - padding));
  const cropRight = Math.min(thumbnail.width, Math.ceil(leftPx + widthPx + padding));
  const cropBottom = Math.min(thumbnail.height, Math.ceil(topPx + heightPx + padding));
  const cropWidth = Math.max(1, cropRight - cropLeft);
  const cropHeight = Math.max(1, cropBottom - cropTop);

  const maxPreviewSize = 220;
  const baseScale = Math.min(maxPreviewSize / cropWidth, maxPreviewSize / cropHeight);
  const scale = Math.max(1.2, Math.min(4, baseScale));

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

export function PhotoFaceAssignmentModal({
  isOpen,
  face,
  region,
  thumbnail,
  people,
  onClose,
  onFaceUpdated,
  onPersonCreated
}: PhotoFaceAssignmentModalProps) {
  const [draft, setDraft] = useState("");
  const [candidates, setCandidates] = useState<FaceCandidate[]>([]);
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [candidateError, setCandidateError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen || !face) {
      return;
    }

    setError(null);
    setCandidateError(null);
    setCandidates([]);
    setDraft(face.person_id ? resolvePersonName(people, face.person_id) : "");

    const controller = new AbortController();
    setIsLoadingCandidates(true);

    fetch(`/api/v1/faces/${face.face_id}/candidates`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Candidate request failed (${response.status})`);
        }
        const payload = (await response.json()) as FaceCandidateLookupPayload;
        if (controller.signal.aborted) {
          return;
        }

        const nextCandidates = Array.isArray(payload.candidates) ? payload.candidates : [];
        setCandidates(nextCandidates);
      })
      .catch((caughtError: unknown) => {
        if (!controller.signal.aborted) {
          setCandidateError(caughtError instanceof Error ? caughtError.message : "Could not load face suggestions.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoadingCandidates(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [face, isOpen, people]);

  const peopleByName = useMemo(() => {
    const sorted = [...people].sort((left, right) => left.display_name.localeCompare(right.display_name, "en-US"));
    return sorted;
  }, [people]);

  const normalizedDraft = normalizeName(draft);
  const exactMatch = useMemo(
    () => peopleByName.find((person) => normalizeName(person.display_name) === normalizedDraft) ?? null,
    [normalizedDraft, peopleByName]
  );

  const fuzzyMatches = useMemo(() => {
    if (!normalizedDraft) {
      return peopleByName;
    }
    const startsWithMatches = peopleByName.filter((person) =>
      normalizeName(person.display_name).startsWith(normalizedDraft)
    );
    const containsMatches = peopleByName.filter((person) => {
      const normalized = normalizeName(person.display_name);
      return normalized.includes(normalizedDraft) && !normalized.startsWith(normalizedDraft);
    });
    return [...startsWithMatches, ...containsMatches];
  }, [normalizedDraft, peopleByName]);

  const targetPerson = exactMatch ?? (fuzzyMatches.length === 1 ? fuzzyMatches[0] : null);
  const trimmedDraft = draft.trim();
  const createCandidate = trimmedDraft.length > 0 && !targetPerson ? trimmedDraft : null;
  const cropStyle = buildCropStyle(region, thumbnail);
  const knownCurrentLabel = face ? resolvePersonName(people, face.person_id) : "Unassigned";
  const isBusy = isSubmitting;

  async function saveAndClose() {
    if (!face || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      let targetPersonId = targetPerson?.person_id ?? "";

      if (!targetPersonId && createCandidate) {
        const createResponse = await fetch("/api/v1/people", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ display_name: createCandidate })
        });
        if (!createResponse.ok) {
          const detail = await readErrorDetail(createResponse);
          setError(detail ?? `Create request failed (${createResponse.status}).`);
          return;
        }

        const createdPerson = (await createResponse.json()) as FaceAssignmentModalPerson;
        onPersonCreated(createdPerson);
        targetPersonId = createdPerson.person_id;
      }

      if (!targetPersonId) {
        setError("Type a person name or pick a known person.");
        return;
      }

      if (face.person_id === targetPersonId) {
        onClose();
        return;
      }

      const endpoint =
        face.person_id === null
          ? `/api/v1/faces/${face.face_id}/assignments`
          : `/api/v1/faces/${face.face_id}/corrections`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ person_id: targetPersonId })
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response);
        setError(
          face.person_id === null
            ? mapAssignmentError(response.status, detail)
            : mapCorrectionError(response.status, detail)
        );
        return;
      }

      onFaceUpdated(face.face_id, targetPersonId);
      onClose();
    } catch {
      setError("Could not update face assignment.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!isOpen || !face) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        className="face-assignment-modal-backdrop"
        aria-label="Close face assignment modal"
        onClick={onClose}
      />

      <section className="face-assignment-modal" role="dialog" aria-modal="true" aria-label="Face assignment">
        <div className="face-assignment-modal-header">
          <h3>Face {face.sequence} assignment</h3>
          <button type="button" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="face-assignment-modal-layout">
          <div className="face-assignment-modal-preview">
            <p>Bbox preview</p>
            {thumbnail && cropStyle ? (
              <div className="face-assignment-modal-crop" style={cropStyle.frame}>
                <img
                  src={`data:${thumbnail.mime_type};base64,${thumbnail.data_base64}`}
                  width={thumbnail.width}
                  height={thumbnail.height}
                  style={cropStyle.image}
                  alt={`Face ${face.sequence} cropped preview`}
                />
              </div>
            ) : (
              <div className="face-assignment-modal-crop-placeholder">Preview unavailable</div>
            )}
          </div>

          <div className="face-assignment-modal-controls">
            <p>Current assignment: {knownCurrentLabel}</p>

            <label htmlFor="face-assignment-person-input">Assign person</label>
            <input
              id="face-assignment-person-input"
              aria-label="Assign person"
              list="face-assignment-known-people"
              value={draft}
              disabled={isBusy}
              onChange={(event) => {
                setDraft(event.currentTarget.value);
                setError(null);
              }}
            />
            <datalist id="face-assignment-known-people">
              {peopleByName.map((person) => (
                <option key={person.person_id} value={person.display_name} />
              ))}
            </datalist>

            <div className="face-assignment-modal-actions">
              <button type="button" onClick={onClose} disabled={isBusy}>
                Cancel
              </button>
              <button type="button" onClick={() => void saveAndClose()} disabled={isBusy}>
                {createCandidate ? `Create and assign "${createCandidate}"` : "Save and close"}
              </button>
            </div>

            <section className="face-assignment-modal-suggestions" aria-label="Suggested names">
              <h4>Suggested names</h4>
              {isLoadingCandidates ? <p>Loading suggestions…</p> : null}
              {!isLoadingCandidates && candidateError ? <p>{candidateError}</p> : null}
              {!isLoadingCandidates && !candidateError && candidates.length === 0 ? (
                <p>No candidate suggestions available.</p>
              ) : null}
              {!isLoadingCandidates && !candidateError && candidates.length > 0 ? (
                <ul>
                  {candidates.map((candidate) => (
                    <li key={candidate.person_id}>
                      <button
                        type="button"
                        onClick={() => {
                          setDraft(candidate.display_name);
                          setError(null);
                        }}
                        disabled={isBusy}
                      >
                        {candidate.display_name} ({formatConfidence(candidate.confidence)})
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>

            {error ? <p className="detail-face-assignment-error">{error}</p> : null}
          </div>
        </div>
      </section>
    </>
  );
}

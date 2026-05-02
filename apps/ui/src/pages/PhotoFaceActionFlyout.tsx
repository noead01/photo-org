import { useEffect, useMemo, useState } from "react";

type FaceLabelSource = "human_confirmed" | "machine_applied" | "machine_suggested" | null;

const NOT_AVAILABLE = "Not available";

interface FaceActionFace {
  face_id: string;
  person_id: string | null;
  label_source?: FaceLabelSource;
  confidence?: number | null;
  model_version?: string | null;
  provenance?: Record<string, unknown> | null;
  label_recorded_ts?: string | null;
}

interface FaceActionPerson {
  person_id: string;
  display_name: string;
  created_ts?: string;
  updated_ts?: string;
}

interface PhotoFaceActionFlyoutProps {
  faces: FaceActionFace[];
  people: FaceActionPerson[];
  requestedFaceActionFaceId?: string | null;
  onFaceUpdated: (faceId: string, personId: string) => void;
  onPersonCreated: (person: FaceActionPerson) => void;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall back to default message mapping.
  }
  return null;
}

function normalizeName(value: string): string {
  return value.trim().toLowerCase();
}

function resolvePersonLabel(people: FaceActionPerson[], personId: string): string {
  const match = people.find((person) => person.person_id === personId);
  return match ? match.display_name : personId;
}

function provenanceSourceLabel(source: FaceLabelSource | undefined): string {
  if (source === "human_confirmed") {
    return "Human confirmed";
  }
  if (source === "machine_applied") {
    return "Machine applied";
  }
  if (source === "machine_suggested") {
    return "Machine suggested";
  }
  return "Unknown";
}

function readProvenanceValue(face: FaceActionFace, key: string): string {
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

export function PhotoFaceActionFlyout({
  faces,
  people,
  requestedFaceActionFaceId = null,
  onFaceUpdated,
  onPersonCreated
}: PhotoFaceActionFlyoutProps) {
  const indexedFaces = useMemo(
    () => faces.map((face, index) => ({ ...face, sequence: index + 1 })),
    [faces]
  );
  const [selectedFaceId, setSelectedFaceId] = useState<string | null>(indexedFaces[0]?.face_id ?? null);
  const [personDraft, setPersonDraft] = useState("");
  const [selectedPersonId, setSelectedPersonId] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (indexedFaces.length === 0) {
      setSelectedFaceId(null);
      return;
    }
    setSelectedFaceId((current) =>
      current && indexedFaces.some((face) => face.face_id === current) ? current : indexedFaces[0].face_id
    );
  }, [indexedFaces]);

  useEffect(() => {
    if (!requestedFaceActionFaceId) {
      return;
    }
    if (!indexedFaces.some((face) => face.face_id === requestedFaceActionFaceId)) {
      return;
    }
    setSelectedFaceId(requestedFaceActionFaceId);
    setPersonDraft("");
    setSelectedPersonId("");
    setError(null);
  }, [requestedFaceActionFaceId, indexedFaces]);

  const selectedFace = indexedFaces.find((face) => face.face_id === selectedFaceId) ?? null;
  const normalizedDraft = normalizeName(personDraft);
  const exactMatch = useMemo(
    () => people.find((person) => normalizeName(person.display_name) === normalizedDraft) ?? null,
    [people, normalizedDraft]
  );

  const orderedPeople = useMemo(() => {
    const sortedPeople = [...people].sort((left, right) =>
      left.display_name.localeCompare(right.display_name, "en-US")
    );
    if (!normalizedDraft) {
      return sortedPeople;
    }

    const suggestions: FaceActionPerson[] = [];
    const others: FaceActionPerson[] = [];
    for (const person of sortedPeople) {
      if (normalizeName(person.display_name).includes(normalizedDraft)) {
        suggestions.push(person);
      } else {
        others.push(person);
      }
    }
    suggestions.sort((left, right) => {
      const leftStarts = normalizeName(left.display_name).startsWith(normalizedDraft) ? 0 : 1;
      const rightStarts = normalizeName(right.display_name).startsWith(normalizedDraft) ? 0 : 1;
      if (leftStarts !== rightStarts) {
        return leftStarts - rightStarts;
      }
      return left.display_name.localeCompare(right.display_name, "en-US");
    });
    return [...suggestions, ...others];
  }, [people, normalizedDraft]);

  const trimmedDraft = personDraft.trim();
  const createCandidate = trimmedDraft.length > 0 && !exactMatch ? trimmedDraft : null;
  const selectedExistingPerson = orderedPeople.find((person) => person.person_id === selectedPersonId) ?? null;
  const targetExistingPersonId = selectedExistingPerson?.person_id ?? exactMatch?.person_id ?? "";
  const canApply =
    !isSubmitting &&
    selectedFace !== null &&
    (targetExistingPersonId.length > 0 || createCandidate !== null);

  async function applySelection() {
    if (!selectedFace) {
      return;
    }

    setIsSubmitting(true);
    setMessage(null);
    setError(null);

    try {
      let nextPersonId = targetExistingPersonId;
      let nextPersonName = selectedExistingPerson?.display_name ?? exactMatch?.display_name ?? createCandidate ?? "";
      if (!nextPersonId && createCandidate) {
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
        const createdPerson = (await createResponse.json()) as FaceActionPerson;
        onPersonCreated(createdPerson);
        nextPersonId = createdPerson.person_id;
        nextPersonName = createdPerson.display_name;
      }

      if (!nextPersonId) {
        return;
      }

      if (selectedFace.person_id !== null && selectedFace.person_id === nextPersonId) {
        setMessage(`Face ${selectedFace.sequence} already maps to ${nextPersonName}.`);
        return;
      }

      const endpoint =
        selectedFace.person_id === null
          ? `/api/v1/faces/${selectedFace.face_id}/assignments`
          : `/api/v1/faces/${selectedFace.face_id}/corrections`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ person_id: nextPersonId })
      });
      if (!response.ok) {
        const detail = await readErrorDetail(response);
        setError(detail ?? `Face update request failed (${response.status}).`);
        return;
      }

      if (selectedFace.person_id === null) {
        setMessage(`Face assignment saved for face ${selectedFace.sequence}.`);
      } else {
        const payload = (await response.json()) as { previous_person_id?: string; person_id?: string };
        const previousId = payload.previous_person_id ?? selectedFace.person_id;
        const updatedId = payload.person_id ?? nextPersonId;
        setMessage(
          `Correction recorded: ${resolvePersonLabel(people, previousId)} -> ${resolvePersonLabel(people, updatedId)}.`
        );
      }

      onFaceUpdated(selectedFace.face_id, nextPersonId);
      setSelectedPersonId("");
      setPersonDraft("");
    } catch {
      setError("Could not update face assignment.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (indexedFaces.length === 0) {
    return (
      <section className="detail-face-actions" aria-label="Face actions">
        <h3>Face actions</h3>
        <p className="detail-face-assignment-complete">No detected faces for this photo.</p>
      </section>
    );
  }

  return (
    <section className="detail-face-actions" aria-label="Face actions">
      <h3>Face actions</h3>
      <ul className="detail-face-action-list">
        {indexedFaces.map((face) => (
          <li key={face.face_id}>
            <button
              type="button"
              className={selectedFaceId === face.face_id ? "is-active" : undefined}
              onClick={() => {
                setSelectedFaceId(face.face_id);
                setMessage(null);
                setError(null);
              }}
            >
              Face {face.sequence}
            </button>
          </li>
        ))}
      </ul>

      {selectedFace ? (
        <div className="detail-face-actions-body">
          <p>
            Current label:{" "}
            {selectedFace.person_id ? resolvePersonLabel(people, selectedFace.person_id) : "Unassigned"}
          </p>

          <label htmlFor="detail-face-person-name">Person name</label>
          <input
            id="detail-face-person-name"
            aria-label="Person name"
            value={personDraft}
            onChange={(event) => {
              setPersonDraft(event.target.value);
              setError(null);
              setMessage(null);
            }}
            disabled={isSubmitting}
          />

          <label htmlFor="detail-face-person-suggestions">Person suggestions</label>
          <select
            id="detail-face-person-suggestions"
            aria-label="Person suggestions"
            value={selectedPersonId}
            disabled={isSubmitting}
            onChange={(event) => {
              setSelectedPersonId(event.target.value);
              setError(null);
              setMessage(null);
            }}
          >
            <option value="">Select person</option>
            {orderedPeople.map((person) => (
              <option key={person.person_id} value={person.person_id}>
                {person.display_name}
              </option>
            ))}
          </select>

          <button type="button" disabled={!canApply} onClick={() => void applySelection()}>
            {createCandidate && selectedPersonId.length === 0
              ? `Create and assign "${createCandidate}"`
              : "Assign selected person"}
          </button>

          {message ? <p className="detail-face-correction-provenance">{message}</p> : null}
          {error ? <p className="detail-face-assignment-error">{error}</p> : null}

          <dl className="detail-face-provenance-details" aria-label={`Provenance details for face ${selectedFace.sequence}`}>
            <div>
              <dt>Source</dt>
              <dd>{provenanceSourceLabel(selectedFace.label_source)}</dd>
            </div>
            <div>
              <dt>Action</dt>
              <dd>{readProvenanceValue(selectedFace, "action")}</dd>
            </div>
            <div>
              <dt>Surface</dt>
              <dd>{readProvenanceValue(selectedFace, "surface")}</dd>
            </div>
            <div>
              <dt>Workflow</dt>
              <dd>{readProvenanceValue(selectedFace, "workflow")}</dd>
            </div>
            <div>
              <dt>Model version</dt>
              <dd>{selectedFace.model_version ?? NOT_AVAILABLE}</dd>
            </div>
            <div>
              <dt>Confidence</dt>
              <dd>{formatConfidence(selectedFace.confidence)}</dd>
            </div>
            <div>
              <dt>Recorded</dt>
              <dd>{formatRecordedTimestamp(selectedFace.label_recorded_ts)}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </section>
  );
}

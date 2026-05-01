import { useMemo, useState } from "react";

export interface FaceAssignmentFace {
  face_id: string;
  person_id: string | null;
}

export interface FaceAssignmentPerson {
  person_id: string;
  display_name: string;
}

interface FaceAssignmentControlsProps {
  faces: FaceAssignmentFace[];
  people: FaceAssignmentPerson[];
  onAssigned: (faceId: string, personId: string) => void;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Ignore parsing errors and use fallback message mapping.
  }

  return null;
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

export function FaceAssignmentControls({ faces, people, onAssigned }: FaceAssignmentControlsProps) {
  const unlabeledFaces = useMemo(() => faces.filter((face) => face.person_id === null), [faces]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeFace = unlabeledFaces[activeIndex] ?? null;

  async function assign(faceId: string, personId: string) {
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(`/api/v1/faces/${faceId}/assignments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Face-Validation-Role": "contributor"
        },
        body: JSON.stringify({ person_id: personId })
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response);
        setError(mapAssignmentError(response.status, detail));
        return;
      }

      onAssigned(faceId, personId);
      setActiveIndex((current) => current + 1);
    } catch {
      setError("Could not assign face.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (activeFace === null) {
    return <p className="detail-face-assignment-complete">All visible faces assigned.</p>;
  }

  return (
    <section className="detail-face-assignment" aria-label="Face assignment">
      <h3>Assign detected faces</h3>
      <label htmlFor={`assign-${activeFace.face_id}`}>{`Assign face ${activeIndex + 1}`}</label>
      <select
        id={`assign-${activeFace.face_id}`}
        aria-label={`Assign face ${activeIndex + 1}`}
        disabled={isSubmitting}
        value=""
        onChange={(event) => {
          const personId = event.target.value;
          if (!personId) {
            return;
          }
          void assign(activeFace.face_id, personId);
        }}
      >
        <option value="" disabled>
          Select person
        </option>
        {people.map((person) => (
          <option key={person.person_id} value={person.person_id}>
            {person.display_name}
          </option>
        ))}
      </select>
      {error ? <p className="detail-face-assignment-error">{error}</p> : null}
    </section>
  );
}

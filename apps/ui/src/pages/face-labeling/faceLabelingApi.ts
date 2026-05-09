import {
  mapFaceAssignmentError,
  mapFaceConfirmationError,
  mapFaceCorrectionError,
  mapFaceDismissalError,
  mapUnknownIdentityError,
  readErrorDetail,
} from "./faceLabelingErrors";

export class FaceLabelingApiError extends Error {}

export interface FaceCandidate {
  person_id: string;
  display_name: string;
  confidence: number;
}

interface FaceCandidatesPayload {
  candidates?: FaceCandidate[];
}

type FaceMutationPayload = {
  previous_person_id?: string;
  person_id?: string;
};

type PersonPayload = {
  person_id: string;
  display_name: string;
  created_ts?: string;
  updated_ts?: string;
};

function contributorHeaders(contentType = false): HeadersInit {
  return contentType
    ? {
        "Content-Type": "application/json",
        "X-Face-Validation-Role": "contributor",
      }
    : {
        "X-Face-Validation-Role": "contributor",
      };
}

async function throwMappedError(
  response: Response,
  mapper: (status: number, detail: string | null) => string
): Promise<never> {
  const detail = await readErrorDetail(response);
  throw new FaceLabelingApiError(mapper(response.status, detail));
}

export async function assignFace(faceId: string, personId: string): Promise<FaceMutationPayload> {
  const response = await fetch(`/api/v1/faces/${faceId}/assignments`, {
    method: "POST",
    headers: contributorHeaders(true),
    body: JSON.stringify({ person_id: personId }),
  });
  if (!response.ok) {
    await throwMappedError(response, mapFaceAssignmentError);
  }
  return (await response.json()) as FaceMutationPayload;
}

export async function correctFace(faceId: string, personId: string): Promise<FaceMutationPayload> {
  const response = await fetch(`/api/v1/faces/${faceId}/corrections`, {
    method: "POST",
    headers: contributorHeaders(true),
    body: JSON.stringify({ person_id: personId }),
  });
  if (!response.ok) {
    await throwMappedError(response, mapFaceCorrectionError);
  }
  return (await response.json()) as FaceMutationPayload;
}

export async function markFaceUnknown(faceId: string): Promise<{ person_id: string }> {
  const response = await fetch(`/api/v1/faces/${faceId}/unknown-identities`, {
    method: "POST",
    headers: contributorHeaders(false),
  });
  if (!response.ok) {
    await throwMappedError(response, mapUnknownIdentityError);
  }
  const payload = (await response.json()) as { person_id?: unknown };
  if (typeof payload.person_id !== "string" || payload.person_id.trim().length === 0) {
    throw new FaceLabelingApiError("Unknown-identity response was missing person information.");
  }
  return { person_id: payload.person_id };
}

export async function dismissFace(faceId: string): Promise<void> {
  const response = await fetch(`/api/v1/faces/${faceId}/dismissals`, {
    method: "POST",
    headers: contributorHeaders(false),
  });
  if (!response.ok) {
    await throwMappedError(response, mapFaceDismissalError);
  }
}

export async function confirmFace(faceId: string, personId: string): Promise<void> {
  const response = await fetch(`/api/v1/faces/${faceId}/confirmations`, {
    method: "POST",
    headers: contributorHeaders(true),
    body: JSON.stringify({ person_id: personId }),
  });
  if (!response.ok) {
    await throwMappedError(response, mapFaceConfirmationError);
  }
}

export async function fetchFaceCandidates(
  faceId: string,
  enforceMinConfidence: boolean,
  signal?: AbortSignal
): Promise<FaceCandidate[]> {
  const response = await fetch(
    `/api/v1/faces/${faceId}/candidates?enforce_min_confidence=${enforceMinConfidence}`,
    { signal }
  );
  if (!response.ok) {
    throw new Error(`Candidate request failed (${response.status})`);
  }
  const payload = (await response.json()) as FaceCandidatesPayload;
  return Array.isArray(payload.candidates) ? payload.candidates : [];
}

export async function createPerson(displayName: string): Promise<PersonPayload> {
  const response = await fetch("/api/v1/people", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ display_name: displayName }),
  });
  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new FaceLabelingApiError(detail ?? `Create request failed (${response.status}).`);
  }
  return (await response.json()) as PersonPayload;
}

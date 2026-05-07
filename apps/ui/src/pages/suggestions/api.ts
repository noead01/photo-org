import type { PersonRecord, SuggestionConfirmPayload, SuggestionListPayload } from "./types";

export async function fetchSuggestionsPage(
  page: number,
  pageSize: number,
  minConfidenceThreshold: number,
  excludedPersonIds: string[]
): Promise<SuggestionListPayload> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
  if (minConfidenceThreshold > 0) {
    params.set("min_confidence", String(minConfidenceThreshold));
  }
  for (const personId of excludedPersonIds) {
    params.append("excluded_person_ids", personId);
  }
  const response = await fetch(`/api/v1/suggestions/faces?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Suggestions request failed (${response.status})`);
  }
  return (await response.json()) as SuggestionListPayload;
}

export async function fetchPeopleDirectory(): Promise<PersonRecord[]> {
  const response = await fetch("/api/v1/people");
  if (!response.ok) {
    throw new Error(`People request failed (${response.status})`);
  }
  return (await response.json()) as PersonRecord[];
}

export async function confirmSuggestions(
  faceIds: string[],
  assignments: Array<{ face_id: string; person_id: string }>
): Promise<SuggestionConfirmPayload> {
  const response = await fetch("/api/v1/suggestions/confirmations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Face-Validation-Role": "contributor"
    },
    body: JSON.stringify({ face_ids: faceIds, assignments })
  });
  if (!response.ok) {
    throw new Error(`Confirm request failed (${response.status})`);
  }
  return (await response.json()) as SuggestionConfirmPayload;
}

export async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall through to fallback message.
  }
  return null;
}

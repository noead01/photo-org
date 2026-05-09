import type { PersonRecord, SuggestionConfirmPayload, SuggestionListPayload } from "./types";
import { readErrorDetail } from "../face-labeling/faceLabelingErrors";
import { fetchPeople } from "../people/peopleApi";

const inFlightSuggestionsRequests = new Map<string, Promise<SuggestionListPayload>>();
let inFlightPeopleDirectoryRequest: Promise<PersonRecord[]> | null = null;

export async function fetchSuggestionsPage(
  page: number,
  pageSize: number,
  minConfidenceThreshold: number,
  maxConfidenceThreshold: number,
  excludedPersonIds: string[]
): Promise<SuggestionListPayload> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize)
  });
  if (minConfidenceThreshold > 0) {
    params.set("min_confidence", String(minConfidenceThreshold));
  }
  if (maxConfidenceThreshold < 1) {
    params.set("max_confidence", String(maxConfidenceThreshold));
  }
  for (const personId of excludedPersonIds) {
    params.append("excluded_person_ids", personId);
  }

  const requestUrl = `/api/v1/suggestions/faces?${params.toString()}`;
  const existingRequest = inFlightSuggestionsRequests.get(requestUrl);
  if (existingRequest) {
    return existingRequest;
  }

  const requestPromise = (async () => {
    const response = await fetch(requestUrl);
    if (!response.ok) {
      throw new Error(`Suggestions request failed (${response.status})`);
    }
    return (await response.json()) as SuggestionListPayload;
  })();

  inFlightSuggestionsRequests.set(requestUrl, requestPromise);
  try {
    return await requestPromise;
  } finally {
    inFlightSuggestionsRequests.delete(requestUrl);
  }
}

export async function fetchPeopleDirectory(): Promise<PersonRecord[]> {
  if (inFlightPeopleDirectoryRequest) {
    return inFlightPeopleDirectoryRequest;
  }

  const requestPromise = fetchPeople() as Promise<PersonRecord[]>;

  inFlightPeopleDirectoryRequest = requestPromise;
  try {
    return await requestPromise;
  } finally {
    inFlightPeopleDirectoryRequest = null;
  }
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

export { readErrorDetail };

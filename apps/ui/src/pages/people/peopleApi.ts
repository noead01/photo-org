import { readErrorDetail } from "../face-labeling/faceLabelingErrors";

export type PersonRecord = {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
};

async function errorMessage(response: Response, fallback: string): Promise<string> {
  const detail = await readErrorDetail(response);
  return detail ?? fallback;
}

export async function fetchPeople(signal?: AbortSignal): Promise<PersonRecord[]> {
  const response = await fetch("/api/v1/people", { signal });
  if (!response.ok) {
    throw new Error(`People request failed (${response.status})`);
  }
  return (await response.json()) as PersonRecord[];
}

export async function createPerson(displayName: string): Promise<PersonRecord> {
  const response = await fetch("/api/v1/people", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ display_name: displayName })
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Create request failed (${response.status})`));
  }

  return (await response.json()) as PersonRecord;
}

export async function renamePerson(personId: string, displayName: string): Promise<PersonRecord> {
  const response = await fetch(`/api/v1/people/${personId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ display_name: displayName })
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Rename request failed (${response.status})`));
  }

  return (await response.json()) as PersonRecord;
}

export async function deletePerson(personId: string): Promise<void> {
  const response = await fetch(`/api/v1/people/${personId}`, {
    method: "DELETE"
  });

  if (!response.ok) {
    throw new Error(await errorMessage(response, `Delete request failed (${response.status})`));
  }
}

import type { PersonRecord, PhotoDetailPayload } from "./photoDetailTypes";
import { fetchPeople } from "../people/peopleApi";

export class PhotoDetailRequestError extends Error {
  status: number;

  constructor(status: number) {
    super(`Photo detail request failed (${status})`);
    this.status = status;
    this.name = "PhotoDetailRequestError";
  }
}

export async function fetchPhotoDetail(photoId: string): Promise<PhotoDetailPayload> {
  const response = await fetch(`/api/v1/photos/${photoId}`);
  if (!response.ok) {
    throw new PhotoDetailRequestError(response.status);
  }
  return (await response.json()) as PhotoDetailPayload;
}

export async function fetchPeopleDirectory(signal?: AbortSignal): Promise<PersonRecord[]> {
  return await fetchPeople(signal);
}

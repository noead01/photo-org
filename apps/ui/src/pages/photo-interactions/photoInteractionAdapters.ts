import type { LibraryPhoto } from "../library/libraryRouteTypes";
import type { PhotoDetailPayload } from "../photo-detail/photoDetailTypes";
import type { SuggestionPhoto } from "../suggestions/types";
import type {
  PhotoFace,
  PhotoFaceSuggestion,
  PhotoSummary,
  PhotoThumbnail,
} from "./photoInteractionTypes";

type FaceLike = {
  face_id?: string;
  person_id?: string | null;
  assigned_person?: {
    person_id: string;
    display_name: string;
  } | null;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_w?: number | null;
  bbox_h?: number | null;
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
  label_source?: "human_confirmed" | "machine_suggested" | null;
  confidence?: number | null;
  model_version?: string | null;
  provenance?: Record<string, unknown> | null;
  label_recorded_ts?: string | null;
  suggestions?: Array<{
    person_id: string;
    display_name: string;
    rank?: number | null;
    confidence: number;
    model_version?: string | null;
    provenance?: Record<string, unknown> | null;
  }>;
  top_suggestion?: {
    person_id: string;
    display_name: string;
    confidence: number;
  };
};

function titleFromPath(path: string): string {
  const trimmed = path.trim();
  if (!trimmed) {
    return "Untitled photo";
  }
  const lastSlash = trimmed.lastIndexOf("/");
  if (lastSlash < 0) {
    return trimmed;
  }
  const title = trimmed.slice(lastSlash + 1).trim();
  return title.length > 0 ? title : "Untitled photo";
}

function adaptThumbnail(
  thumbnail:
    | {
        mime_type: string;
        width: number;
        height: number;
        data_base64: string;
      }
    | null
    | undefined
): PhotoThumbnail | null {
  if (!thumbnail) {
    return null;
  }
  return {
    mimeType: thumbnail.mime_type,
    width: thumbnail.width,
    height: thumbnail.height,
    dataBase64: thumbnail.data_base64,
  };
}

function adaptSuggestions(face: FaceLike): PhotoFaceSuggestion[] {
  const explicitSuggestions = Array.isArray(face.suggestions) ? face.suggestions : [];
  const fallbackSuggestion =
    explicitSuggestions.length === 0 && face.top_suggestion
      ? [
          {
            person_id: face.top_suggestion.person_id,
            display_name: face.top_suggestion.display_name,
            rank: 1,
            confidence: face.top_suggestion.confidence,
            model_version: null,
            provenance: null,
          },
        ]
      : [];

  return [...explicitSuggestions, ...fallbackSuggestion].map((suggestion) => ({
    personId: suggestion.person_id,
    displayName: suggestion.display_name,
    rank: suggestion.rank ?? null,
    confidence: suggestion.confidence,
    modelVersion: suggestion.model_version ?? null,
    provenance: suggestion.provenance ?? null,
  }));
}

function adaptFace(face: FaceLike, fallbackFaceId: string): PhotoFace {
  const personId = face.person_id ?? null;
  const labelSource = face.label_source ?? null;
  const assignedPerson =
    face.assigned_person && typeof face.assigned_person.person_id === "string"
      ? {
          personId: face.assigned_person.person_id,
          displayName: face.assigned_person.display_name,
        }
      : null;
  return {
    faceId: face.face_id ?? fallbackFaceId,
    personId,
    assignedPerson,
    bbox: {
      x: face.bbox_x ?? null,
      y: face.bbox_y ?? null,
      width: face.bbox_w ?? null,
      height: face.bbox_h ?? null,
      spaceWidth: face.bbox_space_width ?? null,
      spaceHeight: face.bbox_space_height ?? null,
    },
    labelSource,
    confidence: face.confidence ?? null,
    modelVersion: face.model_version ?? null,
    provenance: face.provenance ?? null,
    labelRecordedTs: face.label_recorded_ts ?? null,
    suggestions: adaptSuggestions(face),
    canAssign: personId === null,
    canCorrect: personId !== null,
    canDismiss: personId === null,
    canConfirm: personId !== null && labelSource === "machine_suggested",
  };
}

export function adaptLibraryPhoto(photo: LibraryPhoto): PhotoSummary {
  return {
    photoId: photo.photo_id,
    path: photo.path,
    title: titleFromPath(photo.path),
    shotTs: photo.shot_ts,
    filesize: photo.filesize,
    people: photo.people ?? [],
    media: {
      thumbnail: adaptThumbnail(photo.thumbnail),
      originalIntent: "detail-only",
      originalAvailability: photo.original
        ? {
            isAvailable: photo.original.is_available,
            availabilityState: photo.original.availability_state,
            lastFailureReason: photo.original.last_failure_reason,
          }
        : null,
    },
    faces: (photo.faces ?? []).map((face, index) =>
      adaptFace(face, `${photo.photo_id}-face-${index + 1}`)
    ),
    albumMembership: null,
    defaultFaceBoxesVisible: false,
  };
}

export function adaptSuggestionPhoto(photo: SuggestionPhoto): PhotoSummary {
  return {
    photoId: photo.photo_id,
    path: photo.path,
    title: titleFromPath(photo.path),
    shotTs: null,
    filesize: null,
    people: [],
    media: {
      thumbnail: adaptThumbnail(photo.thumbnail),
      originalIntent: "detail-only",
      originalAvailability: null,
    },
    faces: photo.faces.map((face, index) =>
      adaptFace(face, `${photo.photo_id}-suggested-face-${index + 1}`)
    ),
    albumMembership: null,
    defaultFaceBoxesVisible: true,
  };
}

export function adaptPhotoDetail(detail: PhotoDetailPayload): PhotoSummary {
  return {
    photoId: detail.photo_id,
    path: detail.path,
    title: titleFromPath(detail.path),
    shotTs: detail.shot_ts,
    filesize: detail.filesize,
    people: detail.people,
    media: {
      thumbnail: adaptThumbnail(detail.thumbnail),
      originalIntent: "auto-load",
      originalAvailability: detail.original
        ? {
            isAvailable: detail.original.is_available,
            availabilityState: detail.original.availability_state,
            lastFailureReason: detail.original.last_failure_reason,
          }
        : null,
    },
    faces: detail.faces.map((face, index) =>
      adaptFace(face, `${detail.photo_id}-face-${index + 1}`)
    ),
    albumMembership: null,
    defaultFaceBoxesVisible: true,
  };
}

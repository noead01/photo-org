export type PhotoOriginalIntent = "detail-only" | "auto-load";

export type FaceLabelSource = "human_confirmed" | "machine_suggested" | null;

export type PhotoThumbnail = {
  mimeType: string;
  width: number;
  height: number;
  dataBase64: string;
};

export type PhotoMedia = {
  thumbnail: PhotoThumbnail | null;
  originalIntent: PhotoOriginalIntent;
  originalAvailability: {
    isAvailable: boolean | null;
    availabilityState: string | null;
    lastFailureReason: string | null;
  } | null;
};

export type PhotoFaceSuggestion = {
  personId: string;
  displayName: string;
  rank: number | null;
  confidence: number;
  modelVersion: string | null;
  provenance: Record<string, unknown> | null;
};

export type PhotoFace = {
  faceId: string;
  personId: string | null;
  assignedPerson?: {
    personId: string;
    displayName: string;
  } | null;
  bbox: {
    x: number | null;
    y: number | null;
    width: number | null;
    height: number | null;
    spaceWidth: number | null;
    spaceHeight: number | null;
  };
  labelSource: FaceLabelSource;
  confidence: number | null;
  modelVersion: string | null;
  provenance: Record<string, unknown> | null;
  labelRecordedTs: string | null;
  suggestions: PhotoFaceSuggestion[];
  canAssign: boolean;
  canCorrect: boolean;
  canDismiss: boolean;
  canConfirm: boolean;
};

export type PhotoAlbumMembership = {
  albumIds: string[];
  currentAlbumId: string | null;
};

export type PhotoSummary = {
  photoId: string;
  path: string;
  title: string;
  shotTs: string | null;
  filesize: number | null;
  people: string[];
  media: PhotoMedia;
  faces: PhotoFace[];
  albumMembership: PhotoAlbumMembership | null;
  defaultFaceBoxesVisible: boolean;
};

export type AlbumTarget = {
  albumId: string;
  name: string;
  kind: "manual" | "saved_filter";
  canAcceptManualAdditions: boolean;
};

export type FaceSuggestion = {
  person_id: string;
  display_name: string;
  rank: number;
  confidence: number;
  model_version: string | null;
  provenance: Record<string, unknown> | null;
};

export type PhotoDetailFace = {
  face_id: string;
  person_id: string | null;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
  label_source: "human_confirmed" | "machine_suggested" | null;
  confidence: number | null;
  model_version: string | null;
  provenance: Record<string, unknown> | null;
  label_recorded_ts: string | null;
  suggestions?: FaceSuggestion[];
};

export type PhotoDetailPayload = {
  photo_id: string;
  path: string;
  ext: string;
  camera_make: string | null;
  orientation: string | null;
  shot_ts: string | null;
  filesize: number;
  tags: string[];
  people: string[];
  faces: PhotoDetailFace[];
  thumbnail: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
  original: {
    is_available: boolean;
    availability_state: string;
    last_failure_reason: string | null;
  } | null;
  metadata: {
    sha256: string;
    phash: string | null;
    shot_ts_source: string | null;
    camera_model: string | null;
    software: string | null;
    gps_latitude: number | null;
    gps_longitude: number | null;
    gps_altitude: number | null;
    exif_attributes: Record<string, unknown> | null;
    created_ts: string;
    updated_ts: string;
    modified_ts: string | null;
    deleted_ts: string | null;
    faces_count: number;
    faces_detected_ts: string | null;
  };
};

export type PersonRecord = {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
};

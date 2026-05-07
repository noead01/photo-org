export type SuggestionThumbnail = {
  mime_type: string;
  width: number;
  height: number;
  data_base64: string;
};

export type TopSuggestion = {
  person_id: string;
  display_name: string;
  confidence: number;
};

export type RankedSuggestion = TopSuggestion & {
  rank?: number;
};

export type SuggestedFace = {
  face_id: string;
  bbox_x?: number | null;
  bbox_y?: number | null;
  bbox_w?: number | null;
  bbox_h?: number | null;
  bbox_space_width?: number | null;
  bbox_space_height?: number | null;
  top_suggestion: TopSuggestion;
  suggestions: RankedSuggestion[];
};

export type SuggestionPhoto = {
  photo_id: string;
  path: string;
  thumbnail: SuggestionThumbnail | null;
  faces: SuggestedFace[];
};

export type SuggestionListPayload = {
  page: {
    page: number;
    page_size: number;
    total_items: number;
    total_pages: number;
  };
  items: SuggestionPhoto[];
};

export type SuggestionConfirmPayload = {
  assigned: Array<{
    face_id: string;
    photo_id: string;
    person_id: string;
  }>;
  skipped: Array<{
    face_id: string;
    reason: string;
  }>;
};

export type PersonRecord = {
  person_id: string;
  display_name: string;
};

export const UNKNOWN_FACE_CHOICE_LABEL = "Human face (name unknown)";
export const NOT_A_FACE_CHOICE_LABEL = "Not a face (false positive)";

export type FaceChoiceResolution =
  | { kind: "assign_person"; personId: string }
  | { kind: "create_person_and_assign"; displayName: string }
  | { kind: "unknown_human" }
  | { kind: "dismiss_false_positive" }
  | { kind: "empty" };

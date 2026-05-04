import type { SearchFacetPayload } from "../search/facetFilters";

export type SortDirection = "asc" | "desc";
export type PersonCertaintyMode = "human_only" | "include_suggestions";

export type LibraryPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
  people?: string[];
  faces?: Array<{
    person_id: string | null;
    label_source?: "human_confirmed" | "machine_suggested" | null;
    confidence?: number | null;
    suggestions?: Array<{
      person_id: string;
      display_name: string;
      rank: number;
      confidence: number;
      model_version: string | null;
      provenance: Record<string, unknown> | null;
    }>;
  }>;
  thumbnail?: {
    mime_type: string;
    width: number;
    height: number;
    data_base64: string;
  } | null;
  original?: {
    is_available: boolean;
    availability_state: string;
    last_failure_reason: string | null;
  } | null;
};

export type SearchResponsePayload = {
  hits: {
    total: number;
    items: LibraryPhoto[];
    cursor: string | null;
  };
  facets?: SearchFacetPayload;
};

export type PersonRecord = {
  person_id: string;
  display_name: string;
};

export type LibraryLocationRadius = {
  latitude: number;
  longitude: number;
  radius_km: number;
};

export type SearchUrlState = {
  queryChips: string[];
  fromDate: string;
  toDate: string;
  pageSize: number;
  selectedPersonNames: string[];
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
  latitudeDraft: string;
  longitudeDraft: string;
  radiusDraft: string;
  locationRadius: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
};

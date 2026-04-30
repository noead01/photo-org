export type IngestStatusTone = "complete" | "pending" | "failed" | "unknown";

export type IngestStatusViewModel = {
  tone: IngestStatusTone;
  label: string;
  description: string;
};

type IngestStatusInput = {
  availabilityState?: string | null;
  isAvailable?: boolean | null;
  lastFailureReason?: string | null;
  hasThumbnail?: boolean | null;
  facesDetectedTs?: string | null;
  includeFaceDetection?: boolean;
};

const FAILED_AVAILABILITY_STATES = new Set(["unreachable", "disabled", "error", "failed"]);
const ACTIVE_AVAILABILITY_STATE = "active";

function normalizeAvailabilityState(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  return value.trim().toLowerCase();
}

export function deriveIngestStatus(input: IngestStatusInput): IngestStatusViewModel {
  const availabilityState = normalizeAvailabilityState(input.availabilityState);
  const hasFailureReason = Boolean(input.lastFailureReason && input.lastFailureReason.trim());
  const checkFaces = input.includeFaceDetection === true;
  const facesPending = checkFaces && input.facesDetectedTs === null;
  const thumbnailPending = input.hasThumbnail === false;

  if (hasFailureReason || availabilityState !== null && FAILED_AVAILABILITY_STATES.has(availabilityState)) {
    return {
      tone: "failed",
      label: "Failed",
      description: "Ingest reported a failure for this photo or source."
    };
  }

  if (availabilityState !== null && availabilityState !== ACTIVE_AVAILABILITY_STATE) {
    return {
      tone: "unknown",
      label: "Unknown",
      description: `Ingest returned an unrecognized state (${availabilityState}).`
    };
  }

  if (facesPending || thumbnailPending) {
    return {
      tone: "pending",
      label: "Pending",
      description: "Ingest is still processing required assets for this photo."
    };
  }

  if (availabilityState === ACTIVE_AVAILABILITY_STATE || input.isAvailable === true || input.hasThumbnail === true) {
    return {
      tone: "complete",
      label: "Complete",
      description: "Ingest completed enough work for browse and detail rendering."
    };
  }

  if (input.isAvailable === false) {
    return {
      tone: "failed",
      label: "Failed",
      description: "Ingest reported a failure for this photo or source."
    };
  }

  return {
    tone: "unknown",
    label: "Unknown",
    description: "Ingest status is missing from this response."
  };
}

export const INGEST_STATUS_LEGEND: Array<{ tone: IngestStatusTone; label: string; description: string }> = [
  {
    tone: "complete",
    label: "Complete",
    description: "Assets are ready for normal browse/detail viewing."
  },
  {
    tone: "pending",
    label: "Pending",
    description: "Background ingest is still processing this item."
  },
  {
    tone: "failed",
    label: "Failed",
    description: "Ingest encountered a failure for this item or source."
  },
  {
    tone: "unknown",
    label: "Unknown",
    description: "Status was absent or not recognized in the API payload."
  }
];

import type { PhotoFace, PhotoFaceSuggestion } from "./photoInteractionTypes";

export type FaceConfidenceIndicator = "unknown" | "assigned" | "empty" | "low" | "medium" | "strong";

export function resolveTopSuggestion(suggestions: PhotoFaceSuggestion[]): PhotoFaceSuggestion | null {
  if (!Array.isArray(suggestions) || suggestions.length === 0) {
    return null;
  }

  return [...suggestions].sort((left, right) => {
    const leftRank = left.rank ?? Number.MAX_SAFE_INTEGER;
    const rightRank = right.rank ?? Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    if (right.confidence !== left.confidence) {
      return right.confidence - left.confidence;
    }
    return left.displayName.localeCompare(right.displayName, "en-US");
  })[0] ?? null;
}

function isUnknownAssigned(face: PhotoFace): boolean {
  if (!face.personId) {
    return false;
  }
  const assignedDisplayName = face.assignedPerson?.displayName?.toLowerCase() ?? "";
  const personId = face.personId.toLowerCase();
  return assignedDisplayName.includes("unknown") || personId.includes("unknown");
}

export function resolveFaceConfidenceIndicator(face: PhotoFace): FaceConfidenceIndicator {
  if (isUnknownAssigned(face)) {
    return "unknown";
  }

  if (face.personId) {
    return "assigned";
  }

  const topSuggestion = resolveTopSuggestion(face.suggestions);
  if (!topSuggestion) {
    return "empty";
  }
  if (topSuggestion.confidence < 0.4) {
    return "empty";
  }
  if (topSuggestion.confidence < 0.6) {
    return "low";
  }
  if (topSuggestion.confidence < 0.8) {
    return "medium";
  }
  return "strong";
}

export function buildFaceActionSummary(face: PhotoFace): string | null {
  if (isUnknownAssigned(face)) {
    return null;
  }

  if (face.personId) {
    const matchingSuggestion = face.suggestions.find((suggestion) => suggestion.personId === face.personId) ?? null;
    return face.assignedPerson?.displayName ?? matchingSuggestion?.displayName ?? face.personId;
  }

  const topSuggestion = resolveTopSuggestion(face.suggestions);
  if (!topSuggestion) {
    return "Unassigned";
  }
  return topSuggestion.displayName;
}

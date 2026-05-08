const SUGGESTIONS_FILTERS_KEY = "photo-org:suggestions:filters";

export interface StoredSuggestionsFilterState {
  minConfidencePercent: number;
  maxConfidencePercent: number;
  excludedPersonIds: string[];
}

function resolveLocalStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isValidMinConfidencePercent(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 100;
}

function sanitizeExcludedPersonIds(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const normalized = value
    .filter((entry): entry is string => typeof entry === "string")
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0);
  return normalized.length === value.length ? normalized : null;
}

export function loadSuggestionsFilterState(): StoredSuggestionsFilterState | null {
  const storage = resolveLocalStorage();
  if (!storage) {
    return null;
  }

  const rawValue = storage.getItem(SUGGESTIONS_FILTERS_KEY);
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as {
      minConfidencePercent?: unknown;
      maxConfidencePercent?: unknown;
      excludedPersonIds?: unknown;
    };

    if (!isValidMinConfidencePercent(parsed.minConfidencePercent)) {
      return null;
    }
    const maxConfidencePercent =
      parsed.maxConfidencePercent === undefined ? 100 : parsed.maxConfidencePercent;
    if (!isValidMinConfidencePercent(maxConfidencePercent)) {
      return null;
    }

    const excludedPersonIds = sanitizeExcludedPersonIds(parsed.excludedPersonIds);
    if (!excludedPersonIds) {
      return null;
    }

    const minConfidencePercent = parsed.minConfidencePercent;
    return {
      minConfidencePercent,
      maxConfidencePercent: Math.max(maxConfidencePercent, minConfidencePercent),
      excludedPersonIds
    };
  } catch {
    return null;
  }
}

export function saveSuggestionsFilterState(state: StoredSuggestionsFilterState): void {
  const storage = resolveLocalStorage();
  if (!storage) {
    return;
  }

  storage.setItem(
    SUGGESTIONS_FILTERS_KEY,
    JSON.stringify({
      minConfidencePercent: state.minConfidencePercent,
      maxConfidencePercent: state.maxConfidencePercent,
      excludedPersonIds: state.excludedPersonIds
    })
  );
}

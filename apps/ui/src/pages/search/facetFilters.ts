export type FacetCountEntry = {
  value: string;
  count: number;
};

export type SearchFacetPayload = {
  has_faces?: Record<string, unknown>;
  path_hints?: FacetCountEntry[];
  tags?: FacetCountEntry[];
};

export type HasFacesFacetCounts = {
  true: number;
  false: number;
};

function normalizeFacetCount(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    return value;
  }
  return 0;
}

function parseFacetCountEntries(rawEntries: unknown): FacetCountEntry[] {
  if (!Array.isArray(rawEntries)) {
    return [];
  }

  return rawEntries.flatMap((entry) => {
    if (!entry || typeof entry !== "object") {
      return [];
    }

    const value = "value" in entry && typeof entry.value === "string" ? entry.value.trim() : "";
    if (!value) {
      return [];
    }

    const count = "count" in entry ? normalizeFacetCount(entry.count) : 0;
    return [{ value, count }];
  });
}

export function parseHasFacesFacetCounts(facets: SearchFacetPayload | undefined): HasFacesFacetCounts {
  return {
    true: normalizeFacetCount(facets?.has_faces?.true),
    false: normalizeFacetCount(facets?.has_faces?.false)
  };
}

export function toPathHintFacetCounts(
  facets: SearchFacetPayload | undefined,
  activePathHints: string[]
): FacetCountEntry[] {
  const directPathHintCounts = parseFacetCountEntries(facets?.path_hints);
  const sourceCounts =
    directPathHintCounts.length > 0
      ? directPathHintCounts
      : parseFacetCountEntries(facets?.tags)
          .filter((entry) => entry.value.startsWith("event:"))
          .map((entry) => ({ value: entry.value.slice("event:".length), count: entry.count }));

  const mergedCounts = new Map<string, number>();
  for (const entry of sourceCounts) {
    mergedCounts.set(entry.value, (mergedCounts.get(entry.value) ?? 0) + entry.count);
  }
  for (const activePathHint of activePathHints) {
    if (!mergedCounts.has(activePathHint)) {
      mergedCounts.set(activePathHint, 0);
    }
  }

  return [...mergedCounts.entries()]
    .map(([value, count]) => ({ value, count }))
    .sort((left, right) => {
      if (right.count !== left.count) {
        return right.count - left.count;
      }
      return left.value.localeCompare(right.value);
    });
}

export function normalizePathHintFilters(pathHints: string[]): string[] {
  return [...new Set(pathHints.map((hint) => hint.trim()).filter((hint) => hint.length > 0))].sort(
    (left, right) => left.localeCompare(right)
  );
}

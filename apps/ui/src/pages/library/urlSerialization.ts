export function dedupeTrimmedValues(values: string[]): string[] {
  const seen = new Set<string>();
  const deduped: string[] = [];

  for (const value of values) {
    const trimmed = value.trim();
    if (!trimmed || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    deduped.push(trimmed);
  }

  return deduped;
}

export function parsePositiveIntParam(search: string, key: string, defaultValue = 1): number {
  const rawValue = new URLSearchParams(search).get(key);
  if (!rawValue) {
    return defaultValue;
  }

  const parsed = Number.parseInt(rawValue, 10);
  if (!Number.isFinite(parsed) || parsed < 1) {
    return defaultValue;
  }

  return parsed;
}

export function parseNullableBooleanParam(rawValue: string | null): boolean | null {
  const candidate = (rawValue ?? "").trim();
  if (candidate === "true") {
    return true;
  }
  if (candidate === "false") {
    return false;
  }
  return null;
}

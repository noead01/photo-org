const EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS = 30;

export const MISSING_VALUE = "Not available";

export function formatTimestamp(value: string | null): string {
  if (!value) {
    return MISSING_VALUE;
  }

  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(parsed);
}

export function formatFilesize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

export function formatGps(lat: number | null, lon: number | null): string {
  if (lat === null || lon === null) {
    return MISSING_VALUE;
  }

  return `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
}

export function formatOptionalText(value: string | null): string {
  return value && value.trim().length > 0 ? value : MISSING_VALUE;
}

export function formatExifAttributeValue(value: unknown): string {
  const renderedValue = (() => {
    if (value === null) {
      return "null";
    }
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  })();

  if (renderedValue.length <= EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS) {
    return renderedValue;
  }
  return `${renderedValue.slice(0, EXIF_ATTRIBUTE_PREVIEW_MAX_CHARS)}...`;
}

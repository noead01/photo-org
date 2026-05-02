export function formatShotTimestamp(shotTs: string | null): string {
  if (!shotTs) {
    return "Unknown capture time";
  }

  const timestamp = Date.parse(shotTs);
  if (Number.isNaN(timestamp)) {
    return shotTs;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC"
  }).format(timestamp);
}

export function formatFilesize(filesize: number): string {
  if (filesize < 1024) {
    return `${filesize} B`;
  }

  const kb = filesize / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }

  const mb = kb / 1024;
  return `${mb.toFixed(1)} MB`;
}

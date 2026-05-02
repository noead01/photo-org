function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function isLibraryActionConflictActive(payload: unknown): boolean {
  if (!isRecord(payload)) {
    return false;
  }

  const ingestQueue = payload.ingest_queue;
  if (!isRecord(ingestQueue)) {
    return false;
  }

  const summary = ingestQueue.summary;
  if (!isRecord(summary)) {
    return false;
  }

  const processingCount = summary.processing_count;
  return typeof processingCount === "number" && processingCount > 0;
}

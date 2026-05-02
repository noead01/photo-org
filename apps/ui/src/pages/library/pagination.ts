export const INVALID_PAGE_MESSAGE = "Reset to page 1 because that page position is unavailable.";

export function buildFirstPageCursorMap(nextCursor: string | null): Record<number, string | null> {
  const cursorMap: Record<number, string | null> = { 1: null };
  if (nextCursor !== null) {
    cursorMap[2] = nextCursor;
  }
  return cursorMap;
}

export function updateCursorByPage(
  current: Record<number, string | null>,
  page: number,
  pageCursor: string | null,
  nextCursor: string | null
): Record<number, string | null> {
  const next = { ...current, [page]: pageCursor };
  if (nextCursor === null) {
    delete next[page + 1];
  } else {
    next[page + 1] = nextCursor;
  }
  return next;
}

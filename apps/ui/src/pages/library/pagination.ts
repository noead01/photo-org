export const INVALID_PAGE_MESSAGE = "Reset to page 1 because that page position is unavailable.";

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

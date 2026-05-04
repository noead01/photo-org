export const DEFAULT_SEARCH_PAGE_LIMIT = 60;
export const SEARCH_PAGE_LIMIT_OPTIONS = [24, 60, 120] as const;

export type SearchPageLimit = (typeof SEARCH_PAGE_LIMIT_OPTIONS)[number];

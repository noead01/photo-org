import type { RefObject } from "react";
import type { SortDirection } from "./libraryRouteTypes";

interface LibraryRouteHeaderProps {
  headingRef: RefObject<HTMLHeadingElement>;
  sortDirection: SortDirection;
  requestedPage: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  onSortDirectionChange: (direction: SortDirection) => void;
  onPreviousPage: () => void;
  onNextPage: () => void;
}

export function LibraryRouteHeader({
  headingRef,
  sortDirection,
  requestedPage,
  canGoPrevious,
  canGoNext,
  onSortDirectionChange,
  onPreviousPage,
  onNextPage
}: LibraryRouteHeaderProps) {
  return (
    <div className="browse-header">
      <div>
        <h1 id="page-title" ref={headingRef} tabIndex={-1}>
          Library
        </h1>
        <p>Unified library workflow for search, scope, and action surfaces.</p>
      </div>
      <div className="browse-controls" role="group" aria-label="Library controls">
        <label className="browse-sort-control">
          Sort order
          <select
            aria-label="Sort order"
            value={sortDirection}
            onChange={(event) => {
              const nextDirection = event.target.value === "asc" ? "asc" : "desc";
              onSortDirectionChange(nextDirection);
            }}
          >
            <option value="desc">Newest first</option>
            <option value="asc">Oldest first</option>
          </select>
        </label>
        <div className="browse-pagination" aria-label="Pagination controls">
          <button
            type="button"
            onClick={onPreviousPage}
            disabled={!canGoPrevious}
            aria-label="Previous page"
          >
            Previous
          </button>
          <p className="browse-page-indicator">Page {requestedPage}</p>
          <button
            type="button"
            onClick={onNextPage}
            disabled={!canGoNext}
            aria-label="Next page"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

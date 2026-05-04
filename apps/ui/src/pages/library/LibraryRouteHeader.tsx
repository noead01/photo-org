import type { RefObject } from "react";
import { LibraryPageNavigator } from "./LibraryPageNavigator";
import { LibrarySortControl } from "./LibrarySortControl";
import type { SortDirection } from "./libraryRouteTypes";

interface LibraryRouteHeaderProps {
  headingRef: RefObject<HTMLHeadingElement>;
  sortDirection: SortDirection;
  requestedPage: number;
  lastKnownPage: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  pageSize: number;
  pageSizeOptions: readonly number[];
  onSortDirectionChange: (direction: SortDirection) => void;
  onSelectPage: (pageNumber: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function LibraryRouteHeader({
  headingRef,
  sortDirection,
  requestedPage,
  lastKnownPage,
  canGoPrevious,
  canGoNext,
  pageSize,
  pageSizeOptions,
  onSortDirectionChange,
  onSelectPage,
  onPageSizeChange
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
        <LibrarySortControl
          sortDirection={sortDirection}
          onSortDirectionChange={onSortDirectionChange}
        />
        <LibraryPageNavigator
          requestedPage={requestedPage}
          lastKnownPage={lastKnownPage}
          canGoPrevious={canGoPrevious}
          canGoNext={canGoNext}
          pageSize={pageSize}
          pageSizeOptions={pageSizeOptions}
          onSelectPage={onSelectPage}
          onPageSizeChange={onPageSizeChange}
        />
      </div>
    </div>
  );
}

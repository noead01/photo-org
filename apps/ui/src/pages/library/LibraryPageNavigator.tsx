import { BrowsePagination } from "../shared/BrowsePagination";

interface LibraryPageNavigatorProps {
  requestedPage: number;
  lastKnownPage: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  pageSize: number;
  pageSizeOptions: readonly number[];
  onSelectPage: (pageNumber: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

export function LibraryPageNavigator({
  requestedPage,
  lastKnownPage,
  canGoPrevious,
  canGoNext,
  pageSize,
  pageSizeOptions,
  onSelectPage,
  onPageSizeChange
}: LibraryPageNavigatorProps) {
  return (
    <div className="browse-pagination" aria-label="Pagination controls">
      <label className="browse-page-size-control">
        Photos per page
        <select
          aria-label="Photos per page"
          value={String(pageSize)}
          onChange={(event) => onPageSizeChange(Number.parseInt(event.currentTarget.value, 10))}
        >
          {pageSizeOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      <BrowsePagination
        currentPage={requestedPage}
        pageCount={lastKnownPage}
        canGoPrevious={canGoPrevious}
        canGoNext={canGoNext}
        ariaLabel="Library pagination"
        onPageChange={onSelectPage}
      />
    </div>
  );
}

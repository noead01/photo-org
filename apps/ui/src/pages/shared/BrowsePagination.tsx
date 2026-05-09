import ReactPaginate from "react-paginate";

export interface BrowsePaginationProps {
  currentPage: number;
  pageCount: number;
  canGoPrevious: boolean;
  canGoNext: boolean;
  ariaLabel: string;
  onPageChange: (page: number) => void;
}

export function BrowsePagination({
  currentPage,
  pageCount,
  canGoPrevious,
  canGoNext,
  ariaLabel,
  onPageChange,
}: BrowsePaginationProps) {
  const normalizedPageCount = Number.isInteger(pageCount) && pageCount > 0 ? pageCount : 1;
  const normalizedCurrentPage = Number.isInteger(currentPage) && currentPage > 0 ? currentPage : 1;
  const clampedCurrentPage = Math.min(normalizedCurrentPage, normalizedPageCount);

  return (
    <nav className="browse-pagination" aria-label={ariaLabel}>
      <ReactPaginate
        previousLabel="<"
        nextLabel=">"
        breakLabel="..."
        breakAriaLabels={{ backward: "Jump backward", forward: "Jump forward" }}
        pageCount={normalizedPageCount}
        pageRangeDisplayed={3}
        marginPagesDisplayed={1}
        forcePage={clampedCurrentPage - 1}
        disableInitialCallback
        renderOnZeroPageCount={null}
        onClick={(clickEvent) => {
          if (!canGoPrevious && !canGoNext) {
            return false;
          }
          if (clickEvent.isPrevious && !canGoPrevious) {
            return false;
          }
          if (clickEvent.isNext && !canGoNext) {
            return false;
          }
          return undefined;
        }}
        onPageChange={({ selected }) => onPageChange(selected + 1)}
        pageLabelBuilder={(page) => `[${page}]`}
        ariaLabelBuilder={(page) => `Page ${page}`}
        containerClassName="browse-pagination-pages"
        pageClassName="browse-pagination-page-item"
        pageLinkClassName="browse-pagination-page-link"
        previousClassName="browse-pagination-page-item"
        nextClassName="browse-pagination-page-item"
        previousLinkClassName="browse-pagination-page-link browse-pagination-arrow"
        nextLinkClassName="browse-pagination-page-link browse-pagination-arrow"
        activeClassName="is-active"
        disabledClassName="is-disabled"
        breakClassName="browse-pagination-break-item"
        breakLinkClassName="browse-pagination-ellipsis"
      />
    </nav>
  );
}

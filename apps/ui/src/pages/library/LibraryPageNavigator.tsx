import ReactPaginate from "react-paginate";

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
      <ReactPaginate
        previousLabel="<"
        nextLabel=">"
        breakLabel="..."
        breakAriaLabels={{ backward: "Jump backward", forward: "Jump forward" }}
        pageCount={lastKnownPage}
        pageRangeDisplayed={3}
        marginPagesDisplayed={1}
        forcePage={Math.max(0, requestedPage - 1)}
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
        onPageChange={({ selected }) => onSelectPage(selected + 1)}
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
    </div>
  );
}

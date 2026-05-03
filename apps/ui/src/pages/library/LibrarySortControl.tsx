import type { SortDirection } from "./libraryRouteTypes";

interface LibrarySortControlProps {
  sortDirection: SortDirection;
  onSortDirectionChange: (direction: SortDirection) => void;
}

export function LibrarySortControl({
  sortDirection,
  onSortDirectionChange
}: LibrarySortControlProps) {
  return (
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
  );
}

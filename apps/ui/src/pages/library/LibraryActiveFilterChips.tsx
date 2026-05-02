import { formatLocationChipLabel } from "../search/locationFilter";
import type { LibraryLocationRadius } from "./libraryRouteTypes";

interface LibraryActiveFilterChipsProps {
  committedQuery: string;
  fromDate: string;
  toDate: string;
  selectedPersonNames: string[];
  locationRadius: LibraryLocationRadius | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  onClearLocationFilter: () => void;
  onRemovePersonFilter: (displayName: string) => void;
  onClearHasFacesFilter: () => void;
  onClearPathHintFilter: (pathHint: string) => void;
  onClearFromDate: () => void;
  onClearToDate: () => void;
  onClearCommittedQuery: () => void;
}

export function LibraryActiveFilterChips({
  committedQuery,
  fromDate,
  toDate,
  selectedPersonNames,
  locationRadius,
  hasFacesFilter,
  pathHintFilters,
  onClearLocationFilter,
  onRemovePersonFilter,
  onClearHasFacesFilter,
  onClearPathHintFilter,
  onClearFromDate,
  onClearToDate,
  onClearCommittedQuery
}: LibraryActiveFilterChipsProps) {
  const hasAnyFilter =
    Boolean(committedQuery) ||
    Boolean(fromDate || toDate) ||
    selectedPersonNames.length > 0 ||
    Boolean(locationRadius) ||
    hasFacesFilter !== null ||
    pathHintFilters.length > 0;

  if (!hasAnyFilter) {
    return null;
  }

  return (
    <ul className="search-chip-list" aria-label="Active search filters">
      {locationRadius ? (
        <li>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove ${formatLocationChipLabel({
              latitude: locationRadius.latitude,
              longitude: locationRadius.longitude,
              radiusKm: locationRadius.radius_km
            })}`}
            onClick={onClearLocationFilter}
          >
            {formatLocationChipLabel({
              latitude: locationRadius.latitude,
              longitude: locationRadius.longitude,
              radiusKm: locationRadius.radius_km
            })}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ) : null}
      {selectedPersonNames.map((displayName) => (
        <li key={displayName}>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove person ${displayName}`}
            onClick={() => onRemovePersonFilter(displayName)}
          >
            person: {displayName}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ))}
      {hasFacesFilter !== null ? (
        <li>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove has faces filter ${hasFacesFilter ? "with faces" : "without faces"}`}
            onClick={onClearHasFacesFilter}
          >
            has faces: {hasFacesFilter ? "yes" : "no"}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ) : null}
      {pathHintFilters.map((pathHint) => (
        <li key={pathHint}>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove path hint ${pathHint}`}
            onClick={() => onClearPathHintFilter(pathHint)}
          >
            path hint: {pathHint}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ))}
      {fromDate ? (
        <li>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove from date ${fromDate}`}
            onClick={onClearFromDate}
          >
            from: {fromDate}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ) : null}
      {toDate ? (
        <li>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove to date ${toDate}`}
            onClick={onClearToDate}
          >
            to: {toDate}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ) : null}
      {committedQuery ? (
        <li>
          <button
            type="button"
            className="search-chip"
            aria-label={`Remove query ${committedQuery}`}
            onClick={onClearCommittedQuery}
          >
            {committedQuery}
            <span aria-hidden="true"> ×</span>
          </button>
        </li>
      ) : null}
    </ul>
  );
}

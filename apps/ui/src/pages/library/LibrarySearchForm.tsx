import type { FormEventHandler } from "react";
import type { FacetCountEntry } from "../search/facetFilters";
import { FacetFilterPanel } from "../search/FacetFilterPanel";
import { LocationRadiusPicker } from "../search/LocationRadiusPicker";
import type { LocationRadiusValue } from "../search/types";
import type { PersonRecord } from "./libraryRouteTypes";

interface LibrarySearchFormProps {
  queryInput: string;
  fromDate: string;
  toDate: string;
  personDraft: string;
  latitudeDraft: string;
  longitudeDraft: string;
  radiusDraft: string;
  locationRadius: LocationRadiusValue | null;
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  facetHasFacesCounts: { true: number; false: number };
  facetPathHintCounts: FacetCountEntry[];
  dateRangeError: string | null;
  locationError: string | null;
  personMessage: string | null;
  mapMessage: string | null;
  matchingPeople: PersonRecord[];
  onSubmit: FormEventHandler<HTMLFormElement>;
  onQueryInputChange: (value: string) => void;
  onFromDateChange: (value: string) => void;
  onToDateChange: (value: string) => void;
  onPersonDraftChange: (value: string) => void;
  onAddPersonFilter: () => void;
  onAddPersonByName: (displayName: string) => void;
  onLatitudeDraftChange: (value: string) => void;
  onLongitudeDraftChange: (value: string) => void;
  onRadiusDraftChange: (value: string) => void;
  onMapLocationChange: (locationValue: LocationRadiusValue) => void;
  onMapError: (message: string | null) => void;
  onToggleHasFacesFilter: (nextValue: boolean) => void;
  onClearHasFacesFilter: () => void;
  onTogglePathHintFilter: (pathHint: string) => void;
  onClearAllPathHints: () => void;
}

export function LibrarySearchForm({
  queryInput,
  fromDate,
  toDate,
  personDraft,
  latitudeDraft,
  longitudeDraft,
  radiusDraft,
  locationRadius,
  hasFacesFilter,
  pathHintFilters,
  facetHasFacesCounts,
  facetPathHintCounts,
  dateRangeError,
  locationError,
  personMessage,
  mapMessage,
  matchingPeople,
  onSubmit,
  onQueryInputChange,
  onFromDateChange,
  onToDateChange,
  onPersonDraftChange,
  onAddPersonFilter,
  onAddPersonByName,
  onLatitudeDraftChange,
  onLongitudeDraftChange,
  onRadiusDraftChange,
  onMapLocationChange,
  onMapError,
  onToggleHasFacesFilter,
  onClearHasFacesFilter,
  onTogglePathHintFilter,
  onClearAllPathHints
}: LibrarySearchFormProps) {
  return (
    <form className="search-query-form" onSubmit={onSubmit}>
      <div className="search-query-row">
        <input
          aria-label="Search query"
          value={queryInput}
          onChange={(event) => onQueryInputChange(event.target.value)}
        />
        <button type="submit">Search</button>
      </div>

      <div className="search-date-row">
        <label htmlFor="search-date-from">From date</label>
        <input
          id="search-date-from"
          type="date"
          value={fromDate}
          onChange={(event) => onFromDateChange(event.target.value)}
          aria-describedby="search-date-validation"
        />
        <label htmlFor="search-date-to">To date</label>
        <input
          id="search-date-to"
          type="date"
          value={toDate}
          onChange={(event) => onToDateChange(event.target.value)}
          aria-describedby="search-date-validation"
        />
      </div>

      <div className="search-person-row">
        <label htmlFor="search-person-input">Person filter</label>
        <div className="search-person-input-row">
          <input
            id="search-person-input"
            type="text"
            value={personDraft}
            onChange={(event) => onPersonDraftChange(event.target.value)}
            aria-describedby="search-person-validation"
          />
          <button type="button" onClick={onAddPersonFilter}>
            Add person filter
          </button>
        </div>
      </div>

      <div className="search-location-panel">
        <p className="search-filter-section-label">Location radius</p>
        <div className="search-location-row">
          <label htmlFor="search-location-latitude">Latitude</label>
          <input
            id="search-location-latitude"
            type="text"
            inputMode="decimal"
            value={latitudeDraft}
            onChange={(event) => onLatitudeDraftChange(event.target.value)}
            aria-describedby="search-location-validation"
          />
          <label htmlFor="search-location-longitude">Longitude</label>
          <input
            id="search-location-longitude"
            type="text"
            inputMode="decimal"
            value={longitudeDraft}
            onChange={(event) => onLongitudeDraftChange(event.target.value)}
            aria-describedby="search-location-validation"
          />
          <label htmlFor="search-location-radius">Radius (km)</label>
          <input
            id="search-location-radius"
            type="text"
            inputMode="decimal"
            value={radiusDraft}
            onChange={(event) => onRadiusDraftChange(event.target.value)}
            aria-describedby="search-location-validation"
          />
        </div>
        <LocationRadiusPicker value={locationRadius} onChange={onMapLocationChange} onMapError={onMapError} />
      </div>

      <FacetFilterPanel
        hasFacesFilter={hasFacesFilter}
        pathHintFilters={pathHintFilters}
        hasFacesCounts={facetHasFacesCounts}
        pathHintCounts={facetPathHintCounts}
        onToggleHasFaces={onToggleHasFacesFilter}
        onClearHasFaces={onClearHasFacesFilter}
        onTogglePathHint={onTogglePathHintFilter}
        onClearAllPathHints={onClearAllPathHints}
      />

      {dateRangeError ? (
        <p id="search-date-validation" className="search-validation-message" role="alert">
          {dateRangeError}
        </p>
      ) : null}
      {locationError ? (
        <p id="search-location-validation" className="search-validation-message" role="alert">
          {locationError}
        </p>
      ) : null}
      {personMessage ? (
        <p id="search-person-validation" className="search-validation-message" role="status">
          {personMessage}
        </p>
      ) : null}
      {mapMessage ? (
        <p className="search-map-message" role="status">
          {mapMessage}
        </p>
      ) : null}
      {personMessage?.startsWith("Multiple people match") && matchingPeople.length > 0 ? (
        <ul className="search-person-suggestion-list" aria-label="Person suggestions">
          {matchingPeople.map((person) => (
            <li key={person.person_id}>
              <button
                type="button"
                className="search-person-suggestion"
                onClick={() => onAddPersonByName(person.display_name)}
              >
                {person.display_name}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </form>
  );
}

import { useEffect, useState, type FormEventHandler } from "react";
import { ConfidenceSingleSlider } from "../shared/ConfidenceSlider";
import type { FacetCountEntry } from "../search/facetFilters";
import { LocationRadiusPicker } from "../search/LocationRadiusPicker";
import type { LocationRadiusValue } from "../search/types";
import type { PersonCertaintyMode, PersonRecord } from "./libraryRouteTypes";

type OpenFilterPanel = "date" | "person" | "location" | "album" | "pathHints" | null;

interface LibrarySearchFormProps {
  queryInput: string;
  fromDate: string;
  toDate: string;
  personDraft: string;
  selectedPersonNames: string[];
  selectedAlbumIds: string[];
  albumFilterOptions: Array<{ albumId: string; albumName: string }>;
  personCertaintyMode: PersonCertaintyMode;
  suggestionConfidenceMinDraft: string;
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
  onPersonCertaintyModeChange: (value: PersonCertaintyMode) => void;
  onSuggestionConfidenceMinDraftChange: (value: string) => void;
  onLatitudeDraftChange: (value: string) => void;
  onLongitudeDraftChange: (value: string) => void;
  onRadiusDraftChange: (value: string) => void;
  onMapLocationChange: (locationValue: LocationRadiusValue) => void;
  onMapError: (message: string | null) => void;
  onToggleHasFacesFilter: (nextValue: boolean) => void;
  onClearHasFacesFilter: () => void;
  onToggleAlbumFilter: (albumId: string) => void;
  onClearAllAlbumFilters: () => void;
  onTogglePathHintFilter: (pathHint: string) => void;
  onClearAllPathHints: () => void;
}

export function LibrarySearchForm({
  queryInput,
  fromDate,
  toDate,
  personDraft,
  selectedPersonNames,
  selectedAlbumIds,
  albumFilterOptions,
  personCertaintyMode,
  suggestionConfidenceMinDraft,
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
  onPersonCertaintyModeChange,
  onSuggestionConfidenceMinDraftChange,
  onLatitudeDraftChange,
  onLongitudeDraftChange,
  onRadiusDraftChange,
  onMapLocationChange,
  onMapError,
  onToggleHasFacesFilter,
  onClearHasFacesFilter,
  onToggleAlbumFilter,
  onClearAllAlbumFilters,
  onTogglePathHintFilter,
  onClearAllPathHints
}: LibrarySearchFormProps) {
  const [openFilterPanel, setOpenFilterPanel] = useState<OpenFilterPanel>(null);
  const [dateSnapshot, setDateSnapshot] = useState<{ fromDate: string; toDate: string } | null>(null);
  const [isDateAutoCloseArmed, setIsDateAutoCloseArmed] = useState(false);
  const [locationSnapshot, setLocationSnapshot] = useState<{
    latitudeDraft: string;
    longitudeDraft: string;
    radiusDraft: string;
  } | null>(null);
  const suggestionThresholdPercent = normalizeSuggestionThresholdPercent(suggestionConfidenceMinDraft);
  const hasDateFilter = Boolean(fromDate || toDate);
  const hasPersonFilter = hasSelectedPersonFilter(selectedPersonNames, personDraft);
  const hasLocationFilter = Boolean(locationRadius || latitudeDraft || longitudeDraft || radiusDraft);
  const hasAlbumFilter = selectedAlbumIds.length > 0;
  const hasPathHintFilter = pathHintFilters.length > 0;

  useEffect(() => {
    if (openFilterPanel !== "date") {
      return;
    }
    if (!isDateAutoCloseArmed || !fromDate || !toDate || dateRangeError) {
      return;
    }
    setOpenFilterPanel(null);
  }, [dateRangeError, fromDate, isDateAutoCloseArmed, openFilterPanel, toDate]);

  function handleFilterPanelClick(panel: Exclude<OpenFilterPanel, null>) {
    const isOpening = openFilterPanel !== panel;
    if (isOpening && panel === "date") {
      setDateSnapshot({ fromDate, toDate });
      setIsDateAutoCloseArmed(false);
    }
    if (isOpening && panel === "location") {
      setLocationSnapshot({ latitudeDraft, longitudeDraft, radiusDraft });
    }
    setOpenFilterPanel(isOpening ? panel : null);
  }

  function handleHasFacesChipClick() {
    if (hasFacesFilter === null) {
      onToggleHasFacesFilter(true);
      return;
    }
    if (hasFacesFilter === true) {
      onToggleHasFacesFilter(false);
      return;
    }
    onClearHasFacesFilter();
  }

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

      <div className="search-filter-disclosure">
        <div className="search-filter-summary" aria-label="Filter labels">
          <span className="search-filter-summary-title">Filter labels</span>
          <span className="search-filter-summary-line">
            <button
              type="button"
              className={hasDateFilter ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Date filter type"
              onClick={() => handleFilterPanelClick("date")}
            >
              Date
            </button>
            <button
              type="button"
              className={hasPersonFilter ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Person filter type"
              onClick={() => handleFilterPanelClick("person")}
            >
              Person
            </button>
            <button
              type="button"
              className={hasLocationFilter ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Location filter type"
              onClick={() => handleFilterPanelClick("location")}
            >
              Location
            </button>
            <button
              type="button"
              className={hasAlbumFilter ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Album filter type"
              onClick={() => handleFilterPanelClick("album")}
            >
              Album
            </button>
            <button
              type="button"
              className={hasPathHintFilter ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Path hints filter type"
              onClick={() => handleFilterPanelClick("pathHints")}
            >
              Path hints
            </button>
            <button
              type="button"
              className={hasFacesFilter !== null ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
              aria-label="Has faces filter type"
              title={`With faces: ${facetHasFacesCounts.true}, Without faces: ${facetHasFacesCounts.false}`}
              onClick={handleHasFacesChipClick}
            >
              Has faces
            </button>
          </span>
        </div>

        {openFilterPanel === "date" ? (
          <div className="search-filter-content">
            <div className="search-date-row">
              <label htmlFor="search-date-from">From date</label>
              <input
                id="search-date-from"
                type="date"
                value={fromDate}
                onChange={(event) => {
                  setIsDateAutoCloseArmed(true);
                  onFromDateChange(event.target.value);
                }}
                aria-describedby="search-date-validation"
              />
              <label htmlFor="search-date-to">To date</label>
              <input
                id="search-date-to"
                type="date"
                value={toDate}
                onChange={(event) => {
                  setIsDateAutoCloseArmed(true);
                  onToDateChange(event.target.value);
                }}
                aria-describedby="search-date-validation"
              />
            </div>
            <div className="search-person-input-row">
              <button
                type="button"
                onClick={() => {
                  if (dateSnapshot) {
                    onFromDateChange(dateSnapshot.fromDate);
                    onToDateChange(dateSnapshot.toDate);
                  }
                  setOpenFilterPanel(null);
                }}
              >
                Cancel date filters
              </button>
            </div>
          </div>
        ) : null}

        {openFilterPanel === "person" ? (
          <div className="search-filter-content">
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
              <div className="search-person-input-row">
                <label htmlFor="search-person-certainty-mode">Person certainty mode</label>
                <select
                  id="search-person-certainty-mode"
                  aria-label="Person certainty mode"
                  value={personCertaintyMode}
                  onChange={(event) =>
                    onPersonCertaintyModeChange(event.target.value as PersonCertaintyMode)
                  }
                >
                  <option value="human_only">Human-reviewed only</option>
                  <option value="include_suggestions">Include suggestions above threshold</option>
                </select>
              </div>
              {personCertaintyMode === "include_suggestions" ? (
                <div className="search-person-input-row">
                  <ConfidenceSingleSlider
                    value={suggestionThresholdPercent}
                    onValueChange={(value) =>
                      onSuggestionConfidenceMinDraftChange(formatSuggestionThresholdDraft(value))
                    }
                    disabled={false}
                  />
                </div>
              ) : null}
            </div>
            <div className="search-person-input-row">
              <button type="button" onClick={() => setOpenFilterPanel(null)}>
                Done person filters
              </button>
            </div>
          </div>
        ) : null}

        {openFilterPanel === "location" ? (
          <div className="search-filter-content">
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
            <div className="search-person-input-row">
              <button
                type="button"
                onClick={() => {
                  if (!locationError) {
                    setOpenFilterPanel(null);
                  }
                }}
              >
                Apply location filters
              </button>
              <button
                type="button"
                onClick={() => {
                  if (locationSnapshot) {
                    onLatitudeDraftChange(locationSnapshot.latitudeDraft);
                    onLongitudeDraftChange(locationSnapshot.longitudeDraft);
                    onRadiusDraftChange(locationSnapshot.radiusDraft);
                  }
                  setOpenFilterPanel(null);
                }}
              >
                Cancel location filters
              </button>
            </div>
          </div>
        ) : null}

        {openFilterPanel === "album" ? (
          <div className="search-filter-content">
            <div className="search-facet-panel" aria-label="Album filters">
              <p className="search-filter-section-label">Albums</p>
              <div className="search-facet-options">
                {albumFilterOptions.length > 0 ? (
                  albumFilterOptions.map((entry) => {
                    const isActive = selectedAlbumIds.includes(entry.albumId);
                    return (
                      <button
                        key={entry.albumId}
                        type="button"
                        className={`search-facet-option${isActive ? " search-facet-option-active" : ""}`}
                        aria-pressed={isActive}
                        onClick={() => onToggleAlbumFilter(entry.albumId)}
                      >
                        album: {entry.albumName}
                      </button>
                    );
                  })
                ) : (
                  <p className="search-facet-empty">No editable albums yet.</p>
                )}
                {selectedAlbumIds.length > 0 ? (
                  <button type="button" className="search-facet-clear" onClick={onClearAllAlbumFilters}>
                    Clear albums
                  </button>
                ) : null}
              </div>
            </div>
            <div className="search-person-input-row">
              <button type="button" onClick={() => setOpenFilterPanel(null)}>
                Done album filters
              </button>
            </div>
          </div>
        ) : null}

        {openFilterPanel === "pathHints" ? (
          <div className="search-filter-content">
            <div className="search-facet-panel" aria-label="Path hint filters">
              <p className="search-filter-section-label">Path hints</p>
              <div className="search-facet-options">
                {facetPathHintCounts.length > 0 ? (
                  facetPathHintCounts.map((entry) => {
                    const isActive = pathHintFilters.includes(entry.value);
                    return (
                      <button
                        key={entry.value}
                        type="button"
                        className={`search-facet-option${isActive ? " search-facet-option-active" : ""}`}
                        aria-pressed={isActive}
                        onClick={() => onTogglePathHintFilter(entry.value)}
                      >
                        path: {entry.value} ({entry.count})
                      </button>
                    );
                  })
                ) : (
                  <p className="search-facet-empty">Submit a search to load path-hint counts.</p>
                )}
                {pathHintFilters.length > 0 ? (
                  <button type="button" className="search-facet-clear" onClick={onClearAllPathHints}>
                    Clear path hints
                  </button>
                ) : null}
              </div>
            </div>
            <div className="search-person-input-row">
              <button type="button" onClick={() => setOpenFilterPanel(null)}>
                Done path hint filters
              </button>
            </div>
          </div>
        ) : null}
      </div>

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

function normalizeSuggestionThresholdPercent(draft: string): number {
  const parsed = Number.parseFloat(draft);
  if (!Number.isFinite(parsed)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(parsed * 100)));
}

function formatSuggestionThresholdDraft(percent: number): string {
  const normalizedPercent = Math.max(0, Math.min(100, Math.round(percent)));
  const normalizedDecimal = normalizedPercent / 100;
  return normalizedDecimal.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function hasSelectedPersonFilter(selectedPersonNames: string[], personDraft: string): boolean {
  return selectedPersonNames.length > 0 || personDraft.trim().length > 0;
}

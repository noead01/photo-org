import { FormEvent, useEffect, useMemo, useState } from "react";
import { LocationRadiusPicker } from "./search/LocationRadiusPicker";
import { FacetFilterPanel } from "./search/FacetFilterPanel";
import {
  normalizePathHintFilters,
  parseHasFacesFacetCounts,
  toPathHintFacetCounts,
  type FacetCountEntry,
  type SearchFacetPayload
} from "./search/facetFilters";
import {
  buildLocationRadiusFilter,
  formatLocationChipLabel,
  parseLocationDraft,
  validateLocationDraft
} from "./search/locationFilter";
import type { LocationRadiusValue } from "./search/types";

type SearchPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    cursor: string | null;
    items: SearchPhoto[];
  };
  facets?: SearchFacetPayload;
};

type PersonRecord = {
  person_id: string;
  display_name: string;
};

const DEFAULT_SORT = { by: "shot_ts", dir: "desc" } as const;
const DEFAULT_PAGE = { limit: 24, cursor: null } as const;

function buildDateFilter(from: string, to: string): { from?: string; to?: string } | null {
  const trimmedFrom = from.trim();
  const trimmedTo = to.trim();

  if (!trimmedFrom && !trimmedTo) {
    return null;
  }

  return {
    ...(trimmedFrom ? { from: trimmedFrom } : {}),
    ...(trimmedTo ? { to: trimmedTo } : {})
  };
}

function validateDateRange(from: string, to: string): string | null {
  if (from && to && from > to) {
    return "From date must be on or before To date.";
  }

  return null;
}

function normalizeForFuzzyMatch(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function isFuzzyNameMatch(query: string, candidate: string): boolean {
  const normalizedQuery = normalizeForFuzzyMatch(query);
  const normalizedCandidate = normalizeForFuzzyMatch(candidate);

  if (!normalizedQuery || !normalizedCandidate) {
    return false;
  }

  if (normalizedCandidate.includes(normalizedQuery)) {
    return true;
  }

  let queryIndex = 0;
  for (const character of normalizedCandidate) {
    if (character === normalizedQuery[queryIndex]) {
      queryIndex += 1;
      if (queryIndex === normalizedQuery.length) {
        return true;
      }
    }
  }

  return false;
}

function buildSearchFilters(
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null,
  hasFaces: boolean | null,
  pathHints: string[]
): {
  date?: { from?: string; to?: string };
  person_names?: string[];
  location_radius?: { latitude: number; longitude: number; radius_km: number };
  has_faces?: boolean;
  path_hints?: string[];
} | null {
  const dateFilter = buildDateFilter(fromDate, toDate);
  const personNameFilter = selectedPersonNames.length > 0 ? selectedPersonNames : null;
  const locationFilter = locationRadius;
  const pathHintFilter = pathHints.length > 0 ? pathHints : null;

  if (!dateFilter && !personNameFilter && !locationFilter && hasFaces === null && !pathHintFilter) {
    return null;
  }

  return {
    ...(dateFilter ? { date: dateFilter } : {}),
    ...(personNameFilter ? { person_names: personNameFilter } : {}),
    ...(locationFilter ? { location_radius: locationFilter } : {}),
    ...(hasFaces === null ? {} : { has_faces: hasFaces }),
    ...(pathHintFilter ? { path_hints: pathHintFilter } : {})
  };
}

async function fetchSearchResults(
  query: string,
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null,
  hasFaces: boolean | null,
  pathHints: string[]
): Promise<SearchResponsePayload> {
  const searchFilters = buildSearchFilters(
    fromDate,
    toDate,
    selectedPersonNames,
    locationRadius,
    hasFaces,
    pathHints
  );
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      q: query,
      ...(searchFilters ? { filters: searchFilters } : {}),
      sort: DEFAULT_SORT,
      page: DEFAULT_PAGE
    })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

export function SearchRoutePage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [queryChips, setQueryChips] = useState<string[]>([]);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [personDraft, setPersonDraft] = useState("");
  const [selectedPersonNames, setSelectedPersonNames] = useState<string[]>([]);
  const [latitudeDraft, setLatitudeDraft] = useState("");
  const [longitudeDraft, setLongitudeDraft] = useState("");
  const [radiusDraft, setRadiusDraft] = useState("");
  const [peopleDirectory, setPeopleDirectory] = useState<PersonRecord[]>([]);
  const [personMessage, setPersonMessage] = useState<string | null>(null);
  const [mapMessage, setMapMessage] = useState<string | null>(null);
  const [hasFacesFilter, setHasFacesFilter] = useState<boolean | null>(null);
  const [pathHintFilters, setPathHintFilters] = useState<string[]>([]);
  const [facetHasFacesCounts, setFacetHasFacesCounts] = useState<{ true: number; false: number }>({
    true: 0,
    false: 0
  });
  const [facetPathHintCounts, setFacetPathHintCounts] = useState<FacetCountEntry[]>([]);
  const [results, setResults] = useState<SearchPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasRequested, setHasRequested] = useState(false);

  const serializedQuery = useMemo(() => queryChips.join(" "), [queryChips]);
  const dateRangeError = useMemo(() => validateDateRange(fromDate, toDate), [fromDate, toDate]);
  const parsedLocation = useMemo(
    () => parseLocationDraft(latitudeDraft, longitudeDraft, radiusDraft),
    [latitudeDraft, longitudeDraft, radiusDraft]
  );
  const locationError = useMemo(() => validateLocationDraft(parsedLocation), [parsedLocation]);
  const locationRadiusFilter = useMemo(
    () => buildLocationRadiusFilter(parsedLocation),
    [parsedLocation]
  );
  const hasActiveDateFilter = Boolean(fromDate || toDate);
  const hasActivePersonFilter = selectedPersonNames.length > 0;
  const hasActiveLocationFilter = Boolean(locationRadiusFilter);
  const hasActiveHasFacesFilter = hasFacesFilter !== null;
  const hasActivePathHintFilter = pathHintFilters.length > 0;
  const matchingPeople = useMemo(() => {
    const trimmed = personDraft.trim();
    if (!trimmed) {
      return [] as PersonRecord[];
    }

    return peopleDirectory.filter(
      (person) =>
        !selectedPersonNames.includes(person.display_name) &&
        isFuzzyNameMatch(trimmed, person.display_name)
    );
  }, [peopleDirectory, personDraft, selectedPersonNames]);

  useEffect(() => {
    let isCanceled = false;

    async function loadPeopleDirectory() {
      try {
        const response = await fetch("/api/v1/people");
        if (!response.ok) {
          throw new Error();
        }
        const payload = (await response.json()) as PersonRecord[];
        if (!isCanceled) {
          setPeopleDirectory(payload);
        }
      } catch {
        if (!isCanceled) {
          setPersonMessage("People lookup is unavailable. Search can continue without person filters.");
        }
      }
    }

    void loadPeopleDirectory();

    return () => {
      isCanceled = true;
    };
  }, []);

  async function runSearch(
    chips: string[],
    activeFromDate: string,
    activeToDate: string,
    activePersonNames: string[],
    activeLocationRadius: { latitude: number; longitude: number; radius_km: number } | null,
    activeHasFaces: boolean | null,
    activePathHints: string[]
  ) {
    if (validateDateRange(activeFromDate, activeToDate)) {
      return;
    }

    setIsLoading(true);
    setError(null);
    setHasRequested(true);

    try {
      const payload = await fetchSearchResults(
        chips.join(" "),
        activeFromDate,
        activeToDate,
        activePersonNames,
        activeLocationRadius,
        activeHasFaces,
        activePathHints
      );
      setResults(payload.hits.items);
      setTotalCount(payload.hits.total);
      setFacetHasFacesCounts(parseHasFacesFacetCounts(payload.facets));
      setFacetPathHintCounts(toPathHintFacetCounts(payload.facets, activePathHints));
    } catch (caughtError: unknown) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Could not load search results.";
      setError(message);
      setResults([]);
      setTotalCount(0);
      setFacetHasFacesCounts({ true: 0, false: 0 });
      setFacetPathHintCounts(
        activePathHints.map((value) => ({
          value,
          count: 0
        }))
      );
    } finally {
      setIsLoading(false);
    }
  }

  function requestSearch(overrides: {
    chips?: string[];
    fromDate?: string;
    toDate?: string;
    personNames?: string[];
    locationRadius?: { latitude: number; longitude: number; radius_km: number } | null;
    hasFaces?: boolean | null;
    pathHints?: string[];
  } = {}) {
    void runSearch(
      overrides.chips ?? queryChips,
      overrides.fromDate ?? fromDate,
      overrides.toDate ?? toDate,
      overrides.personNames ?? selectedPersonNames,
      overrides.locationRadius === undefined ? locationRadiusFilter : overrides.locationRadius,
      overrides.hasFaces === undefined ? hasFacesFilter : overrides.hasFaces,
      overrides.pathHints ?? pathHintFilters
    );
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (dateRangeError || locationError) {
      return;
    }

    const trimmed = draftQuery.trim();
    if (
      !trimmed &&
      !hasActiveDateFilter &&
      !hasActivePersonFilter &&
      !hasActiveLocationFilter &&
      !hasActiveHasFacesFilter &&
      !hasActivePathHintFilter
    ) {
      return;
    }

    const nextChips = trimmed ? [...queryChips, trimmed] : queryChips;
    if (trimmed) {
      setQueryChips(nextChips);
      setDraftQuery("");
    }

    requestSearch({ chips: nextChips });
  }

  function handleDismissChip(indexToRemove: number) {
    const nextChips = queryChips.filter((_, index) => index !== indexToRemove);
    setQueryChips(nextChips);
    requestSearch({ chips: nextChips });
  }

  function handleClearFromDate() {
    setFromDate("");
    requestSearch({ fromDate: "" });
  }

  function handleClearToDate() {
    setToDate("");
    requestSearch({ toDate: "" });
  }

  function handleAddPersonByName(displayName: string) {
    if (selectedPersonNames.includes(displayName)) {
      setPersonDraft("");
      setPersonMessage(null);
      return;
    }

    setSelectedPersonNames((current) => [...current, displayName]);
    setPersonDraft("");
    setPersonMessage(null);
  }

  function handleAddPersonFilter() {
    const trimmed = personDraft.trim();
    if (!trimmed) {
      return;
    }

    if (matchingPeople.length === 0) {
      setPersonMessage(`No people match "${trimmed}". Search still works without this filter.`);
      return;
    }

    if (matchingPeople.length > 1) {
      setPersonMessage(`Multiple people match "${trimmed}". Select one from suggestions.`);
      return;
    }

    handleAddPersonByName(matchingPeople[0].display_name);
  }

  function handleRemovePersonFilter(displayName: string) {
    const nextNames = selectedPersonNames.filter((name) => name !== displayName);
    setSelectedPersonNames(nextNames);
    setPersonMessage(null);
    requestSearch({ personNames: nextNames });
  }

  function handleMapLocationChange(location: LocationRadiusValue) {
    setLatitudeDraft(String(location.latitude));
    setLongitudeDraft(String(location.longitude));
    setRadiusDraft(String(Number(location.radiusKm.toFixed(3))));
    setMapMessage(null);
  }

  function handleClearLocationFilter() {
    setLatitudeDraft("");
    setLongitudeDraft("");
    setRadiusDraft("");
    requestSearch({ locationRadius: null });
  }

  function handleToggleHasFacesFilter(nextValue: boolean) {
    const resolvedValue = hasFacesFilter === nextValue ? null : nextValue;
    setHasFacesFilter(resolvedValue);
    requestSearch({ hasFaces: resolvedValue });
  }

  function handleClearHasFacesFilter() {
    if (hasFacesFilter === null) {
      return;
    }

    setHasFacesFilter(null);
    requestSearch({ hasFaces: null });
  }

  function handleTogglePathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.includes(pathHint)
      ? pathHintFilters.filter((hint) => hint !== pathHint)
      : normalizePathHintFilters([...pathHintFilters, pathHint]);

    setPathHintFilters(nextHints);
    requestSearch({ pathHints: nextHints });
  }

  function handleClearPathHintFilter(pathHint: string) {
    const nextHints = pathHintFilters.filter((hint) => hint !== pathHint);
    if (nextHints.length === pathHintFilters.length) {
      return;
    }

    setPathHintFilters(nextHints);
    requestSearch({ pathHints: nextHints });
  }

  function handleClearAllPathHints() {
    if (pathHintFilters.length === 0) {
      return;
    }

    setPathHintFilters([]);
    requestSearch({ pathHints: [] });
  }

  function handleRetry() {
    requestSearch();
  }

  const summaryLabel = useMemo(() => {
    if (isLoading) {
      return "Loading search workflow.";
    }

    if (error) {
      return "Search results unavailable.";
    }

    if (!hasRequested) {
      return "Submit a phrase to search the catalog.";
    }

    return `Showing ${results.length} of ${totalCount} photos`;
  }, [error, hasRequested, isLoading, results.length, totalCount]);

  return (
    <section aria-labelledby="page-title" className="page search-page">
      <div>
        <h1 id="page-title">Search</h1>
        <p>Tokenized phrase chips and inclusive date range filters with deterministic request state.</p>
      </div>

      <form className="search-query-form" onSubmit={handleSubmit}>
        <label htmlFor="search-query-input">Search query</label>
        <div className="search-query-row">
          <input
            id="search-query-input"
            type="text"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            aria-describedby="search-query-summary"
          />
          <button type="submit">Search</button>
        </div>
        <div className="search-date-row">
          <label htmlFor="search-date-from">From date</label>
          <input
            id="search-date-from"
            type="date"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
            aria-describedby="search-query-summary search-date-validation"
          />
          <label htmlFor="search-date-to">To date</label>
          <input
            id="search-date-to"
            type="date"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
            aria-describedby="search-query-summary search-date-validation"
          />
        </div>
        <div className="search-person-row">
          <label htmlFor="search-person-input">Person filter</label>
          <div className="search-person-input-row">
            <input
              id="search-person-input"
              type="text"
              value={personDraft}
              onChange={(event) => setPersonDraft(event.target.value)}
              aria-describedby="search-query-summary search-person-validation"
            />
            <button type="button" onClick={handleAddPersonFilter}>
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
              onChange={(event) => setLatitudeDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
            <label htmlFor="search-location-longitude">Longitude</label>
            <input
              id="search-location-longitude"
              type="text"
              inputMode="decimal"
              value={longitudeDraft}
              onChange={(event) => setLongitudeDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
            <label htmlFor="search-location-radius">Radius (km)</label>
            <input
              id="search-location-radius"
              type="text"
              inputMode="decimal"
              value={radiusDraft}
              onChange={(event) => setRadiusDraft(event.target.value)}
              aria-describedby="search-query-summary search-location-validation"
            />
          </div>
          <LocationRadiusPicker
            value={
              locationRadiusFilter
                ? {
                    latitude: locationRadiusFilter.latitude,
                    longitude: locationRadiusFilter.longitude,
                    radiusKm: locationRadiusFilter.radius_km
                  }
                : null
            }
            onChange={handleMapLocationChange}
            onMapError={setMapMessage}
          />
        </div>
        <FacetFilterPanel
          hasFacesFilter={hasFacesFilter}
          pathHintFilters={pathHintFilters}
          hasFacesCounts={facetHasFacesCounts}
          pathHintCounts={facetPathHintCounts}
          onToggleHasFaces={handleToggleHasFacesFilter}
          onClearHasFaces={handleClearHasFacesFilter}
          onTogglePathHint={handleTogglePathHintFilter}
          onClearAllPathHints={handleClearAllPathHints}
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
                  onClick={() => handleAddPersonByName(person.display_name)}
                >
                  {person.display_name}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </form>

      {queryChips.length > 0 ||
      hasActiveDateFilter ||
      hasActivePersonFilter ||
      hasActiveLocationFilter ||
      hasActiveHasFacesFilter ||
      hasActivePathHintFilter ? (
        <ul className="search-chip-list" aria-label="Active search filters">
          {locationRadiusFilter ? (
            <li>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove ${formatLocationChipLabel({
                  latitude: locationRadiusFilter.latitude,
                  longitude: locationRadiusFilter.longitude,
                  radiusKm: locationRadiusFilter.radius_km
                })}`}
                onClick={handleClearLocationFilter}
              >
                {formatLocationChipLabel({
                  latitude: locationRadiusFilter.latitude,
                  longitude: locationRadiusFilter.longitude,
                  radiusKm: locationRadiusFilter.radius_km
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
                onClick={() => handleRemovePersonFilter(displayName)}
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
                onClick={handleClearHasFacesFilter}
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
                onClick={() => handleClearPathHintFilter(pathHint)}
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
                onClick={handleClearFromDate}
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
                onClick={handleClearToDate}
              >
                to: {toDate}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ) : null}
          {queryChips.map((chip, index) => (
            <li key={`${chip}-${index}`}>
              <button
                type="button"
                className="search-chip"
                aria-label={`Remove query ${chip}`}
                onClick={() => handleDismissChip(index)}
              >
                {chip}
                <span aria-hidden="true"> ×</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <p id="search-query-summary" className="search-summary" aria-live="polite">
        {summaryLabel}
      </p>

      {isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading search workflow.
        </div>
      ) : null}

      {error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load Search</h2>
          <p>{error}</p>
          <button type="button" onClick={handleRetry}>
            Retry
          </button>
        </div>
      ) : null}

      {!error && !isLoading && hasRequested && results.length === 0 ? (
        <div className="feedback-panel">
          <p>No matching photos for the active query.</p>
        </div>
      ) : null}

      {!error && !isLoading && results.length > 0 ? (
        <ol className="search-results" aria-label="Search results">
          {results.map((photo) => (
            <li key={photo.photo_id}>
              <h2>{photo.photo_id}</h2>
              <p className="search-result-path" title={photo.path}>
                {photo.path}
              </p>
            </li>
          ))}
        </ol>
      ) : null}

      <p className="search-serialized-query" aria-live="off">
        Active query: {serializedQuery || "(none)"} | Date range:{" "}
        {fromDate || toDate ? `${fromDate || "(open)"} to ${toDate || "(open)"}` : "(none)"}
        {" | People: "}
        {selectedPersonNames.length > 0 ? selectedPersonNames.join(", ") : "(none)"}
        {" | Location: "}
        {locationRadiusFilter
          ? `${locationRadiusFilter.latitude.toFixed(4)}, ${locationRadiusFilter.longitude.toFixed(4)} (${locationRadiusFilter.radius_km.toFixed(1)} km)`
          : "(none)"}
        {" | Has faces: "}
        {hasFacesFilter === null ? "(none)" : hasFacesFilter ? "true" : "false"}
        {" | Path hints: "}
        {pathHintFilters.length > 0 ? pathHintFilters.join(", ") : "(none)"}
      </p>
    </section>
  );
}

import type { FacetCountEntry, HasFacesFacetCounts } from "./facetFilters";

type FacetFilterPanelProps = {
  hasFacesFilter: boolean | null;
  pathHintFilters: string[];
  hasFacesCounts: HasFacesFacetCounts;
  pathHintCounts: FacetCountEntry[];
  onToggleHasFaces: (nextValue: boolean) => void;
  onClearHasFaces: () => void;
  onTogglePathHint: (pathHint: string) => void;
  onClearAllPathHints: () => void;
};

export function FacetFilterPanel({
  hasFacesFilter,
  pathHintFilters,
  hasFacesCounts,
  pathHintCounts,
  onToggleHasFaces,
  onClearHasFaces,
  onTogglePathHint,
  onClearAllPathHints
}: FacetFilterPanelProps) {
  return (
    <div className="search-facet-panel" aria-label="Facet filters">
      <p className="search-filter-section-label">Facet filters</p>
      <div className="search-facet-group">
        <p className="search-facet-group-label">Has faces</p>
        <div className="search-facet-options">
          <button
            type="button"
            className={`search-facet-option${hasFacesFilter === true ? " search-facet-option-active" : ""}`}
            aria-pressed={hasFacesFilter === true}
            onClick={() => onToggleHasFaces(true)}
          >
            With faces ({hasFacesCounts.true})
          </button>
          <button
            type="button"
            className={`search-facet-option${hasFacesFilter === false ? " search-facet-option-active" : ""}`}
            aria-pressed={hasFacesFilter === false}
            onClick={() => onToggleHasFaces(false)}
          >
            Without faces ({hasFacesCounts.false})
          </button>
          {hasFacesFilter !== null ? (
            <button type="button" className="search-facet-clear" onClick={onClearHasFaces}>
              Clear has-faces
            </button>
          ) : null}
        </div>
      </div>
      <div className="search-facet-group">
        <p className="search-facet-group-label">Path hints</p>
        <div className="search-facet-options">
          {pathHintCounts.length > 0 ? (
            pathHintCounts.map((entry) => {
              const isActive = pathHintFilters.includes(entry.value);
              return (
                <button
                  key={entry.value}
                  type="button"
                  className={`search-facet-option${isActive ? " search-facet-option-active" : ""}`}
                  aria-pressed={isActive}
                  onClick={() => onTogglePathHint(entry.value)}
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
    </div>
  );
}

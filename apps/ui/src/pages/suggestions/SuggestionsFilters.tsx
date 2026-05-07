import type { PersonRecord } from "./types";

type SuggestionsFiltersProps = {
  minConfidencePercent: number;
  isLoading: boolean;
  isConfirming: boolean;
  peopleDirectory: PersonRecord[];
  availablePeopleToExclude: PersonRecord[];
  excludedPeople: PersonRecord[];
  excludedPersonPickerValue: string;
  onMinConfidenceChange: (value: number) => void;
  onExcludedPersonPickerValueChange: (value: string) => void;
  onAddExcludedPerson: (personId: string) => void;
  onRemoveExcludedPerson: (personId: string) => void;
};

export function SuggestionsFilters({
  minConfidencePercent,
  isLoading,
  isConfirming,
  peopleDirectory,
  availablePeopleToExclude,
  excludedPeople,
  excludedPersonPickerValue,
  onMinConfidenceChange,
  onExcludedPersonPickerValueChange,
  onAddExcludedPerson,
  onRemoveExcludedPerson
}: SuggestionsFiltersProps) {
  return (
    <div className="suggestions-filter-group">
      <label className="suggestions-confidence-filter">
        <span>{`Minimum certainty: ${minConfidencePercent}%`}</span>
        <input
          type="range"
          min={0}
          max={100}
          step={1}
          value={minConfidencePercent}
          aria-label="Minimum suggestion certainty"
          onChange={(event) => {
            onMinConfidenceChange(Number(event.currentTarget.value));
          }}
          disabled={isLoading || isConfirming}
        />
      </label>
      {peopleDirectory.length > 0 ? (
        <div className="suggestions-people-filter">
          <p className="suggestions-filter-label">Exclude people</p>
          <label className="suggestions-exclude-picker-label" htmlFor="suggestions-exclude-person-picker">
            <span>Add excluded person</span>
            <select
              id="suggestions-exclude-person-picker"
              aria-label="Add excluded person"
              value={excludedPersonPickerValue}
              onChange={(event) => {
                const personId = event.currentTarget.value;
                onExcludedPersonPickerValueChange("");
                if (!personId) {
                  return;
                }
                onAddExcludedPerson(personId);
              }}
              disabled={isLoading || isConfirming || availablePeopleToExclude.length === 0}
            >
              <option value="">Select person</option>
              {availablePeopleToExclude.map((person) => (
                <option key={person.person_id} value={person.person_id}>
                  {person.display_name}
                </option>
              ))}
            </select>
          </label>
          {excludedPeople.length > 0 ? (
            <ul className="search-chip-list suggestions-active-filters" aria-label="Active excluded people">
              {excludedPeople.map((person) => (
                <li key={person.person_id}>
                  <button
                    type="button"
                    className="search-chip search-chip-active"
                    aria-label={`Remove excluded person ${person.display_name}`}
                    onClick={() => onRemoveExcludedPerson(person.person_id)}
                    disabled={isLoading || isConfirming}
                  >
                    {`excluded: ${person.display_name}`}
                    <span aria-hidden="true"> ×</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

import type { PersonRecord } from "./types";
import { ConfidenceRangeSlider } from "../shared/ConfidenceSlider";

type SuggestionsFiltersProps = {
  minConfidencePercent: number;
  maxConfidencePercent: number;
  isLoading: boolean;
  isConfirming: boolean;
  peopleDirectory: PersonRecord[];
  availablePeopleToExclude: PersonRecord[];
  excludedPeople: PersonRecord[];
  excludedPersonPickerValue: string;
  onConfidenceRangeChange: (minValue: number, maxValue: number) => void;
  onExcludedPersonPickerValueChange: (value: string) => void;
  onAddExcludedPerson: (personId: string) => void;
  onRemoveExcludedPerson: (personId: string) => void;
};

export function SuggestionsFilters({
  minConfidencePercent,
  maxConfidencePercent,
  isLoading,
  isConfirming,
  peopleDirectory,
  availablePeopleToExclude,
  excludedPeople,
  excludedPersonPickerValue,
  onConfidenceRangeChange,
  onExcludedPersonPickerValueChange,
  onAddExcludedPerson,
  onRemoveExcludedPerson
}: SuggestionsFiltersProps) {
  return (
    <div className="suggestions-filter-group">
      <div className="suggestions-confidence-filter">
        <ConfidenceRangeSlider
          minValue={minConfidencePercent}
          maxValue={maxConfidencePercent}
          onValueChange={onConfidenceRangeChange}
          disabled={isLoading || isConfirming}
        />
      </div>
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

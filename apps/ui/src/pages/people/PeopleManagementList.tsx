import type { PersonRecord } from "./peopleApi";
import type { BusyAction } from "./peopleState";

interface PeopleManagementListProps {
  people: PersonRecord[];
  renameDraftsByPersonId: Record<string, string>;
  errorByPersonId: Record<string, string>;
  busyByPersonId: Record<string, BusyAction | undefined>;
  onRenameDraftChange: (personId: string, value: string) => void;
  onRename: (personId: string) => void;
  onDelete: (personId: string) => void;
}

export function PeopleManagementList({
  people,
  renameDraftsByPersonId,
  errorByPersonId,
  busyByPersonId,
  onRenameDraftChange,
  onRename,
  onDelete
}: PeopleManagementListProps) {
  return (
    <ul className="people-management-list" aria-label="People records">
      {people.map((person) => {
        const rowError = errorByPersonId[person.person_id];
        const busyAction = busyByPersonId[person.person_id];

        return (
          <li key={person.person_id} className="people-management-item">
            <h2>{person.display_name}</h2>
            <p className="people-management-id">ID: {person.person_id}</p>
            <label htmlFor={`rename-${person.person_id}`}>Display name</label>
            <div className="people-management-actions">
              <input
                id={`rename-${person.person_id}`}
                aria-label={`Display name for person ${person.display_name}`}
                value={renameDraftsByPersonId[person.person_id] ?? person.display_name}
                onChange={(event) => {
                  onRenameDraftChange(person.person_id, event.target.value);
                }}
                disabled={busyAction !== undefined}
              />
              <button
                type="button"
                onClick={() => {
                  onRename(person.person_id);
                }}
                disabled={busyAction !== undefined}
                aria-label={`Rename person ${person.display_name}`}
              >
                Rename
              </button>
              <button
                type="button"
                onClick={() => {
                  onDelete(person.person_id);
                }}
                disabled={busyAction !== undefined}
                aria-label={`Delete person ${person.display_name}`}
              >
                Delete
              </button>
            </div>
            {rowError ? <p className="people-validation-message">{rowError}</p> : null}
          </li>
        );
      })}
    </ul>
  );
}

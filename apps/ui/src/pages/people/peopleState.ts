import type { PersonRecord } from "./peopleApi";

export type { PersonRecord };
export type BusyAction = "rename" | "delete";

export function sortPeopleDirectory(people: PersonRecord[]): PersonRecord[] {
  return [...people].sort((left, right) => {
    const displayNameComparison = left.display_name.localeCompare(right.display_name, "en-US");
    if (displayNameComparison !== 0) {
      return displayNameComparison;
    }
    return left.person_id.localeCompare(right.person_id, "en-US");
  });
}

export function applyPersonUpdate(people: PersonRecord[], updatedPerson: PersonRecord): PersonRecord[] {
  return people.map((person) =>
    person.person_id === updatedPerson.person_id ? updatedPerson : person
  );
}

export function syncPersonRowState(
  people: PersonRecord[],
  currentDrafts: Record<string, string>,
  currentErrors: Record<string, string>,
  currentBusy: Record<string, BusyAction | undefined>
): {
  renameDraftsByPersonId: Record<string, string>;
  errorByPersonId: Record<string, string>;
  busyByPersonId: Record<string, BusyAction | undefined>;
} {
  const renameDraftsByPersonId: Record<string, string> = {};
  const errorByPersonId: Record<string, string> = {};
  const busyByPersonId: Record<string, BusyAction | undefined> = {};

  for (const person of people) {
    renameDraftsByPersonId[person.person_id] =
      currentDrafts[person.person_id] ?? person.display_name;

    if (currentErrors[person.person_id]) {
      errorByPersonId[person.person_id] = currentErrors[person.person_id];
    }

    if (currentBusy[person.person_id]) {
      busyByPersonId[person.person_id] = currentBusy[person.person_id];
    }
  }

  return {
    renameDraftsByPersonId,
    errorByPersonId,
    busyByPersonId
  };
}

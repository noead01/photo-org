import { describe, expect, it } from "vitest";
import {
  applyPersonUpdate,
  sortPeopleDirectory,
  syncPersonRowState,
  type BusyAction,
  type PersonRecord
} from "./peopleState";

function person(personId: string, displayName: string): PersonRecord {
  return {
    person_id: personId,
    display_name: displayName,
    created_ts: "2026-04-20T12:00:00Z",
    updated_ts: "2026-04-20T12:00:00Z"
  };
}

describe("peopleState", () => {
  it("sorts by display name then person id", () => {
    const payload = [
      person("person-2", "Zoe Carter"),
      person("person-10", "Ana Gomez"),
      person("person-1", "Ana Gomez"),
      person("person-3", "Ana Carter")
    ];

    const sorted = sortPeopleDirectory(payload);
    expect(sorted.map((entry) => `${entry.display_name}:${entry.person_id}`)).toEqual([
      "Ana Carter:person-3",
      "Ana Gomez:person-1",
      "Ana Gomez:person-10",
      "Zoe Carter:person-2"
    ]);
  });

  it("applies person updates by id", () => {
    const initial = [person("person-1", "Ana"), person("person-2", "Inez")];
    const updated = person("person-2", "Inez Alvarez");

    expect(applyPersonUpdate(initial, updated)).toEqual([person("person-1", "Ana"), updated]);
  });

  it("syncs drafts and prunes row errors and busy maps for removed people", () => {
    const people = [person("person-1", "Ana"), person("person-2", "Inez")];
    const drafts = {
      "person-1": "Ana Maria",
      "person-3": "Ghost"
    };
    const errors = {
      "person-2": "Could not rename person.",
      "person-3": "Should be removed"
    };
    const busy: Record<string, BusyAction | undefined> = {
      "person-1": "rename",
      "person-3": "delete"
    };

    const next = syncPersonRowState(people, drafts, errors, busy);

    expect(next.renameDraftsByPersonId).toEqual({
      "person-1": "Ana Maria",
      "person-2": "Inez"
    });
    expect(next.errorByPersonId).toEqual({
      "person-2": "Could not rename person."
    });
    expect(next.busyByPersonId).toEqual({
      "person-1": "rename"
    });
  });
});

import { FormEvent, useEffect, useMemo, useState } from "react";

type PersonRecord = {
  person_id: string;
  display_name: string;
  created_ts: string;
  updated_ts: string;
};

type BusyAction = "rename" | "delete";

function sortPeopleDirectory(people: PersonRecord[]): PersonRecord[] {
  return [...people].sort((left, right) => {
    const displayNameComparison = left.display_name.localeCompare(right.display_name, "en-US");
    if (displayNameComparison !== 0) {
      return displayNameComparison;
    }
    return left.person_id.localeCompare(right.person_id, "en-US");
  });
}

async function readErrorDetail(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim().length > 0) {
      return payload.detail;
    }
  } catch {
    // Ignore parsing errors and use fallback.
  }

  return fallback;
}

function applyPersonUpdate(people: PersonRecord[], updatedPerson: PersonRecord): PersonRecord[] {
  return people.map((person) =>
    person.person_id === updatedPerson.person_id ? updatedPerson : person
  );
}

export function PeopleManagementRoutePage() {
  const [people, setPeople] = useState<PersonRecord[]>([]);
  const [renameDraftsByPersonId, setRenameDraftsByPersonId] = useState<Record<string, string>>({});
  const [errorByPersonId, setErrorByPersonId] = useState<Record<string, string>>({});
  const [createDraft, setCreateDraft] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [isCreating, setIsCreating] = useState(false);
  const [busyByPersonId, setBusyByPersonId] = useState<Record<string, BusyAction | undefined>>({});

  useEffect(() => {
    const controller = new AbortController();

    setIsLoading(true);
    setLoadError(null);

    fetch("/api/v1/people", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`People request failed (${response.status})`);
        }

        const payload = (await response.json()) as PersonRecord[];
        const sortedPeople = sortPeopleDirectory(payload);
        setPeople(sortedPeople);
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setLoadError(
          caughtError instanceof Error
            ? caughtError.message
            : "Could not load people directory."
        );
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [reloadToken]);

  useEffect(() => {
    setRenameDraftsByPersonId((current) => {
      const next: Record<string, string> = {};
      for (const person of people) {
        next[person.person_id] = current[person.person_id] ?? person.display_name;
      }
      return next;
    });

    setErrorByPersonId((current) => {
      const next: Record<string, string> = {};
      for (const person of people) {
        if (current[person.person_id]) {
          next[person.person_id] = current[person.person_id];
        }
      }
      return next;
    });

    setBusyByPersonId((current) => {
      const next: Record<string, BusyAction | undefined> = {};
      for (const person of people) {
        if (current[person.person_id]) {
          next[person.person_id] = current[person.person_id];
        }
      }
      return next;
    });
  }, [people]);

  const sortedPeople = useMemo(() => sortPeopleDirectory(people), [people]);

  async function handleCreatePerson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedDisplayName = createDraft.trim();
    if (!trimmedDisplayName) {
      setCreateError("Display name is required.");
      return;
    }

    setCreateError(null);
    setIsCreating(true);

    try {
      const response = await fetch("/api/v1/people", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ display_name: trimmedDisplayName })
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response, `Create request failed (${response.status})`);
        setCreateError(detail);
        return;
      }

      const createdPerson = (await response.json()) as PersonRecord;
      setPeople((current) => sortPeopleDirectory([...current, createdPerson]));
      setCreateDraft("");
    } catch {
      setCreateError("Could not create person.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleRenamePerson(person: PersonRecord) {
    const draft = renameDraftsByPersonId[person.person_id] ?? person.display_name;
    const trimmedDisplayName = draft.trim();

    if (!trimmedDisplayName) {
      setErrorByPersonId((current) => ({
        ...current,
        [person.person_id]: "Display name is required."
      }));
      return;
    }

    setBusyByPersonId((current) => ({ ...current, [person.person_id]: "rename" }));
    setErrorByPersonId((current) => ({ ...current, [person.person_id]: "" }));

    try {
      const response = await fetch(`/api/v1/people/${person.person_id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ display_name: trimmedDisplayName })
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response, `Rename request failed (${response.status})`);
        setErrorByPersonId((current) => ({
          ...current,
          [person.person_id]: detail
        }));
        return;
      }

      const updatedPerson = (await response.json()) as PersonRecord;
      setPeople((current) => sortPeopleDirectory(applyPersonUpdate(current, updatedPerson)));
      setErrorByPersonId((current) => ({ ...current, [person.person_id]: "" }));
    } catch {
      setErrorByPersonId((current) => ({
        ...current,
        [person.person_id]: "Could not rename person."
      }));
    } finally {
      setBusyByPersonId((current) => ({ ...current, [person.person_id]: undefined }));
    }
  }

  async function handleDeletePerson(person: PersonRecord) {
    setBusyByPersonId((current) => ({ ...current, [person.person_id]: "delete" }));
    setErrorByPersonId((current) => ({ ...current, [person.person_id]: "" }));

    try {
      const response = await fetch(`/api/v1/people/${person.person_id}`, {
        method: "DELETE"
      });

      if (!response.ok) {
        const detail = await readErrorDetail(response, `Delete request failed (${response.status})`);
        setErrorByPersonId((current) => ({
          ...current,
          [person.person_id]: detail
        }));
        return;
      }

      setPeople((current) =>
        current.filter((candidate) => candidate.person_id !== person.person_id)
      );
    } catch {
      setErrorByPersonId((current) => ({
        ...current,
        [person.person_id]: "Could not delete person."
      }));
    } finally {
      setBusyByPersonId((current) => ({ ...current, [person.person_id]: undefined }));
    }
  }

  return (
    <section aria-labelledby="page-title" className="page people-management-page">
      <div className="people-management-header">
        <h1 id="page-title">Labeling</h1>
        <p>People management workflows for create, rename, and delete operations.</p>
      </div>

      <section className="people-management-panel" aria-label="Create person">
        <h2>Create person</h2>
        <form className="people-create-form" onSubmit={handleCreatePerson}>
          <label htmlFor="create-person-display-name">Display name</label>
          <div className="people-create-row">
            <input
              id="create-person-display-name"
              aria-label="Create person display name"
              value={createDraft}
              onChange={(event) => {
                setCreateDraft(event.target.value);
                setCreateError(null);
              }}
              disabled={isCreating}
            />
            <button type="submit" disabled={isCreating}>
              Create person
            </button>
          </div>
        </form>
        {createError ? <p className="people-validation-message">{createError}</p> : null}
      </section>

      {loadError ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load people directory</h2>
          <p>{loadError}</p>
          <button type="button" onClick={() => setReloadToken((current) => current + 1)}>
            Retry
          </button>
        </div>
      ) : null}

      {!loadError && isLoading ? (
        <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
          Loading people directory.
        </div>
      ) : null}

      {!loadError && !isLoading && sortedPeople.length === 0 ? (
        <div className="feedback-panel">
          <p>No people yet. Create the first person to start labeling.</p>
        </div>
      ) : null}

      {!loadError && !isLoading && sortedPeople.length > 0 ? (
        <ul className="people-management-list" aria-label="People records">
          {sortedPeople.map((person) => {
            const rowError = errorByPersonId[person.person_id];
            const busyAction = busyByPersonId[person.person_id];

            return (
              <li key={person.person_id} className="people-management-item">
                <h2>{person.display_name}</h2>
                <p className="people-management-id">ID: {person.person_id}</p>
                <label htmlFor={`rename-${person.person_id}`}>
                  Display name
                </label>
                <div className="people-management-actions">
                  <input
                    id={`rename-${person.person_id}`}
                    aria-label={`Display name for person ${person.display_name}`}
                    value={renameDraftsByPersonId[person.person_id] ?? person.display_name}
                    onChange={(event) => {
                      const nextValue = event.target.value;
                      setRenameDraftsByPersonId((current) => ({
                        ...current,
                        [person.person_id]: nextValue
                      }));
                      setErrorByPersonId((current) => ({
                        ...current,
                        [person.person_id]: ""
                      }));
                    }}
                    disabled={busyAction !== undefined}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      void handleRenamePerson(person);
                    }}
                    disabled={busyAction !== undefined}
                    aria-label={`Rename person ${person.display_name}`}
                  >
                    Rename
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      void handleDeletePerson(person);
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
      ) : null}
    </section>
  );
}

import { useEffect, useMemo, useState } from "react";
import {
  createPerson,
  deletePerson,
  fetchPeople,
  renamePerson,
  type PersonRecord
} from "./peopleApi";
import {
  applyPersonUpdate,
  sortPeopleDirectory,
  syncPersonRowState,
  type BusyAction
} from "./peopleState";

export function usePeopleManagement() {
  const [people, setPeople] = useState<PersonRecord[]>([]);
  const [renameDraftsByPersonId, setRenameDraftsByPersonId] = useState<Record<string, string>>({});
  const [errorByPersonId, setErrorByPersonId] = useState<Record<string, string>>({});
  const [createDraft, setCreateDraftState] = useState("");
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

    fetchPeople(controller.signal)
      .then((payload) => {
        setPeople(payload);
        setIsLoading(false);
      })
      .catch((caughtError: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        setLoadError(
          caughtError instanceof Error ? caughtError.message : "Could not load people directory."
        );
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [reloadToken]);

  useEffect(() => {
    const next = syncPersonRowState(people, renameDraftsByPersonId, errorByPersonId, busyByPersonId);
    setRenameDraftsByPersonId(next.renameDraftsByPersonId);
    setErrorByPersonId(next.errorByPersonId);
    setBusyByPersonId(next.busyByPersonId);
  }, [people]);

  const sortedPeople = useMemo(() => sortPeopleDirectory(people), [people]);

  function retryLoad() {
    setReloadToken((current) => current + 1);
  }

  function setCreateDraft(value: string) {
    setCreateDraftState(value);
    setCreateError(null);
  }

  function setRenameDraft(personId: string, nextValue: string) {
    setRenameDraftsByPersonId((current) => ({
      ...current,
      [personId]: nextValue
    }));
    setErrorByPersonId((current) => ({
      ...current,
      [personId]: ""
    }));
  }

  async function createCurrentPerson() {
    const trimmedDisplayName = createDraft.trim();
    if (!trimmedDisplayName) {
      setCreateError("Display name is required.");
      return;
    }

    setCreateError(null);
    setIsCreating(true);

    try {
      const createdPerson = await createPerson(trimmedDisplayName);
      setPeople((current) => [...current, createdPerson]);
      setCreateDraftState("");
    } catch (caughtError) {
      setCreateError(caughtError instanceof Error ? caughtError.message : "Could not create person.");
    } finally {
      setIsCreating(false);
    }
  }

  async function renamePersonById(personId: string) {
    const person = people.find((candidate) => candidate.person_id === personId);
    if (!person) {
      return;
    }

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
      const updatedPerson = await renamePerson(person.person_id, trimmedDisplayName);
      setPeople((current) => applyPersonUpdate(current, updatedPerson));
      setErrorByPersonId((current) => ({ ...current, [person.person_id]: "" }));
    } catch (caughtError) {
      setErrorByPersonId((current) => ({
        ...current,
        [person.person_id]:
          caughtError instanceof Error ? caughtError.message : "Could not rename person."
      }));
    } finally {
      setBusyByPersonId((current) => ({ ...current, [person.person_id]: undefined }));
    }
  }

  async function deletePersonById(personId: string) {
    const person = people.find((candidate) => candidate.person_id === personId);
    if (!person) {
      return;
    }

    setBusyByPersonId((current) => ({ ...current, [person.person_id]: "delete" }));
    setErrorByPersonId((current) => ({ ...current, [person.person_id]: "" }));

    try {
      await deletePerson(person.person_id);
      setPeople((current) => current.filter((candidate) => candidate.person_id !== person.person_id));
    } catch (caughtError) {
      setErrorByPersonId((current) => ({
        ...current,
        [person.person_id]:
          caughtError instanceof Error ? caughtError.message : "Could not delete person."
      }));
    } finally {
      setBusyByPersonId((current) => ({ ...current, [person.person_id]: undefined }));
    }
  }

  return {
    sortedPeople,
    renameDraftsByPersonId,
    errorByPersonId,
    createDraft,
    createError,
    isLoading,
    loadError,
    isCreating,
    busyByPersonId,
    retryLoad,
    setCreateDraft,
    createCurrentPerson,
    setRenameDraft,
    renamePersonById,
    deletePersonById
  };
}

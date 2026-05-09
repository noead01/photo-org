import type { FormEvent } from "react";

interface PeopleCreateFormProps {
  createDraft: string;
  createError: string | null;
  isCreating: boolean;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
}

export function PeopleCreateForm({
  createDraft,
  createError,
  isCreating,
  onDraftChange,
  onSubmit
}: PeopleCreateFormProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <section className="people-management-panel" aria-label="Create person">
      <h2>Create person</h2>
      <form className="people-create-form" onSubmit={handleSubmit}>
        <label htmlFor="create-person-display-name">Display name</label>
        <div className="people-create-row">
          <input
            id="create-person-display-name"
            aria-label="Create person display name"
            value={createDraft}
            onChange={(event) => {
              onDraftChange(event.target.value);
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
  );
}

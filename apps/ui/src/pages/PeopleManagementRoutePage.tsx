import { PeopleCreateForm } from "./people/PeopleCreateForm";
import { PeopleManagementList } from "./people/PeopleManagementList";
import { usePeopleManagement } from "./people/usePeopleManagement";

export function PeopleManagementRoutePage() {
  const {
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
  } = usePeopleManagement();

  return (
    <section aria-labelledby="page-title" className="page people-management-page">
      <div className="people-management-header">
        <h1 id="page-title">Labeling</h1>
        <p>People management workflows for create, rename, and delete operations.</p>
      </div>

      <PeopleCreateForm
        createDraft={createDraft}
        createError={createError}
        isCreating={isCreating}
        onDraftChange={setCreateDraft}
        onSubmit={() => {
          void createCurrentPerson();
        }}
      />

      {loadError ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load people directory</h2>
          <p>{loadError}</p>
          <button type="button" onClick={retryLoad}>
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
        <PeopleManagementList
          people={sortedPeople}
          renameDraftsByPersonId={renameDraftsByPersonId}
          errorByPersonId={errorByPersonId}
          busyByPersonId={busyByPersonId}
          onRenameDraftChange={setRenameDraft}
          onRename={(personId) => {
            void renamePersonById(personId);
          }}
          onDelete={(personId) => {
            void deletePersonById(personId);
          }}
        />
      ) : null}
    </section>
  );
}

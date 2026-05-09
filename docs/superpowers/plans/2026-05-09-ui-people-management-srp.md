# UI People Management SRP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move People Management API access and list mutation logic out of TSX so the route is primarily composition.

**Architecture:** Add a reusable people API module and a route-specific state hook. Split create form and people list into presentational components.

**Tech Stack:** React 18, TypeScript, Fetch API, Vitest, Testing Library.

---

## Files

- Modify: `apps/ui/src/pages/PeopleManagementRoutePage.tsx`
- Create: `apps/ui/src/pages/people/peopleApi.ts`
- Create: `apps/ui/src/pages/people/peopleState.ts`
- Create: `apps/ui/src/pages/people/peopleState.test.ts`
- Create: `apps/ui/src/pages/people/usePeopleManagement.ts`
- Create: `apps/ui/src/pages/people/PeopleCreateForm.tsx`
- Create: `apps/ui/src/pages/people/PeopleManagementList.tsx`
- Modify: `apps/ui/src/pages/PeopleManagementRoutePage.test.tsx`
- Later optional modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Later optional modify: `apps/ui/src/pages/suggestions/api.ts`
- Later optional modify: `apps/ui/src/pages/library/libraryRouteApi.ts`

## Current Problem

`PeopleManagementRoutePage.tsx` directly performs API calls and manages derived list state:

- People list fetch at `apps/ui/src/pages/PeopleManagementRoutePage.tsx:53`.
- Create person fetch at `apps/ui/src/pages/PeopleManagementRoutePage.tsx:120`.
- Rename person fetch at `apps/ui/src/pages/PeopleManagementRoutePage.tsx:157`.
- Delete person fetch at `apps/ui/src/pages/PeopleManagementRoutePage.tsx:203`.
- Draft/error/busy synchronization after people changes at `apps/ui/src/pages/PeopleManagementRoutePage.tsx:88`.

## Tasks

### Task 1: Extract People API

- [ ] Create `peopleApi.ts`.
- [ ] Export `PersonRecord`.
- [ ] Export `fetchPeople`, `createPerson`, `renamePerson`, and `deletePerson`.
- [ ] Move `readErrorDetail` into this module or import it from a shared API utility if available.
- [ ] Preserve current endpoint paths and HTTP methods.
- [ ] Preserve fallback messages:
`People request failed`, `Create request failed`, `Rename request failed`, and `Delete request failed`.

### Task 2: Extract Pure People State Helpers

- [ ] Create `peopleState.ts`.
- [ ] Move `sortPeopleDirectory` and `applyPersonUpdate`.
- [ ] Add `syncPersonRowState(people, currentDrafts, currentErrors, currentBusy)` if keeping draft/error/busy maps.
- [ ] Add tests for sorting by display name then person ID, update by ID, and pruning draft/error/busy maps for deleted people.
- [ ] Run: `npm --prefix apps/ui test -- peopleState.test.ts`.

### Task 3: Extract Management Hook

- [ ] Create `usePeopleManagement.ts`.
- [ ] Move people list state, create draft/error, loading/loadError/reload, busy maps, row errors, and handlers into the hook.
- [ ] Expose stable handler names:
`retryLoad`, `setCreateDraft`, `createCurrentPerson`, `setRenameDraft`, `renamePersonById`, and `deletePersonById`.
- [ ] Keep form event handling out of the hook where practical; hook methods should accept values/IDs.

### Task 4: Extract Create Form

- [ ] Create `PeopleCreateForm.tsx`.
- [ ] Move create person panel/form JSX from the route.
- [ ] Props should include `createDraft`, `createError`, `isCreating`, `onDraftChange`, and `onSubmit`.
- [ ] Preserve labels and aria labels.

### Task 5: Extract People List

- [ ] Create `PeopleManagementList.tsx`.
- [ ] Move list rendering and rename/delete row controls.
- [ ] Props should include people, rename drafts, error map, busy map, and callbacks.
- [ ] Preserve labels and disabled states.

### Task 6: Compose Route and Verify

- [ ] Update `PeopleManagementRoutePage` to use the hook and new components.
- [ ] Route keeps page header and loading/error/empty-state surfaces.
- [ ] Run: `npm --prefix apps/ui test -- PeopleManagementRoutePage.test.tsx`.
- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.

## Acceptance Criteria

- People API access is reusable outside the management page.
- Pure sorting/update/pruning behavior is unit tested outside TSX.
- Route file no longer contains fetch calls.
- Existing create, rename, delete, loading, and error tests pass.


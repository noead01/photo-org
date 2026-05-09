# UI Face Labeling Shared Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove duplicated face-labeling fetch/error/state logic from TSX components by introducing shared domain and API modules.

**Architecture:** Move face assignment API calls, status-to-message mapping, and optimistic face update helpers out of components. Components keep presentation state and invoke intent-level functions.

**Tech Stack:** React 18, TypeScript, Vitest, Fetch API.

---

## Files

- Create: `apps/ui/src/pages/face-labeling/faceLabelingApi.ts`
- Create: `apps/ui/src/pages/face-labeling/faceLabelingErrors.ts`
- Create: `apps/ui/src/pages/face-labeling/faceLabelingState.ts`
- Create: `apps/ui/src/pages/face-labeling/faceLabelingState.test.ts`
- Create: `apps/ui/src/pages/face-labeling/faceLabelingErrors.test.ts`
- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
- Modify: `apps/ui/src/pages/FaceAssignmentControls.tsx`
- Modify: `apps/ui/src/pages/library/LibraryPhotoFacePanel.tsx`
- Modify: `apps/ui/src/pages/suggestions/useSuggestionsActions.ts`

## Current Problem

- `readErrorDetail` is duplicated in `PhotoFaceAssignmentModal`, `FaceAssignmentControls`, `LibraryPhotoFacePanel`, `suggestions/api`, and `libraryRouteApi`.
- Assignment, correction, unknown-human, dismissal, and confirmation endpoint logic is implemented in multiple components.
- `applyFaceAssignment` exists in both `PhotoDetailRoutePage` and `LibraryPhotoFacePanel`.
- Error mappings are repeated across `PhotoFaceAssignmentModal` and `FaceAssignmentControls`.

## Tasks

### Task 1: Extract Error Mapping

- [ ] Create `faceLabelingErrors.ts`.
- [ ] Export `readErrorDetail(response)`.
- [ ] Export mappers:
`mapFaceAssignmentError`, `mapFaceCorrectionError`, `mapFaceDismissalError`, `mapUnknownIdentityError`, `mapFaceConfirmationError`.
- [ ] Use current strings from existing components so snapshots and user-facing behavior remain stable.
- [ ] Add focused tests for 403, 404 with detail, 409 with detail, and fallback status cases.
- [ ] Run: `npm --prefix apps/ui test -- faceLabelingErrors.test.ts`.

### Task 2: Extract Face Labeling API

- [ ] Create `faceLabelingApi.ts`.
- [ ] Export functions:
`assignFace(faceId, personId)`, `correctFace(faceId, personId)`, `markFaceUnknown(faceId)`, `dismissFace(faceId)`, `confirmFace(faceId, personId)`, `fetchFaceCandidates(faceId, enforceMinConfidence)`, `createPerson(displayName)`.
- [ ] Set `"X-Face-Validation-Role": "contributor"` in the shared functions where existing code sends that header.
- [ ] Preserve JSON body shapes currently sent by components.
- [ ] Reuse `readErrorDetail` and the specific error mappers.

### Task 3: Extract Optimistic Face State Helpers

- [ ] Create `faceLabelingState.ts`.
- [ ] Export generic helpers that work with face records containing `face_id`, `person_id`, and optional label provenance fields:
`applyFaceAssignment`, `applyFaceDismissal`, `applyFaceConfirmation`.
- [ ] Ensure assignment clears machine-label provenance fields in the same way current code does.
- [ ] Ensure dismissal removes the face and lets callers update `faces_count` if their payload has metadata.
- [ ] Add tests for assignment, dismissal, and confirmation.
- [ ] Run: `npm --prefix apps/ui test -- faceLabelingState.test.ts`.

### Task 4: Update Face Assignment Modal

- [ ] Replace direct fetch calls in `PhotoFaceAssignmentModal` with shared API functions.
- [ ] Remove local error mapper and `readErrorDetail` definitions.
- [ ] Keep modal-specific draft/candidate/crop UI state inside the component.
- [ ] Run: `npm --prefix apps/ui test -- PhotoDetailRoutePage.test.tsx`.

### Task 5: Update Face Assignment Controls

- [ ] Replace direct fetch calls in `FaceAssignmentControls` with shared API functions.
- [ ] Remove duplicated error mapper and `readErrorDetail` definitions.
- [ ] Keep correction selection and expanded provenance UI state inside the component.
- [ ] Run: `npm --prefix apps/ui test -- FaceAssignmentControls.test.tsx`.

### Task 6: Update Library Photo Face Panel and Suggestions Actions

- [ ] Replace direct confirmation and face-action fetches in `LibraryPhotoFacePanel` and `useSuggestionsActions`.
- [ ] Replace local optimistic state helpers with shared helpers.
- [ ] Keep page reload behavior in Suggestions unchanged.
- [ ] Run: `npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx FaceAssignmentControls.test.tsx`.

### Task 7: Final Verification

- [ ] Run: `rg -n "readErrorDetail|mapAssignmentError|mapCorrectionError|mapUnknownIdentityError|applyFaceAssignment" apps/ui/src/pages -g '*.{ts,tsx}'`.
- [ ] Expected: duplicates are removed or renamed to shared imports.
- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.

## Acceptance Criteria

- Face labeling endpoint details live in one API module.
- Error mapping strings live in one error module.
- Components no longer contain fetch calls for face assignment/correction/unknown/dismissal/confirmation.
- Existing user-facing error messages remain unchanged.


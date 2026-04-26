# ADR-0016: Introduce Face Assignment Correction API Workflow

- Status: Proposed
- Date: 2026-04-25

## Context

Issue #42 introduced first-pass face assignment with conservative semantics:

- `POST /api/v1/faces/{face_id}/assignments`
- assign only when `faces.person_id IS NULL`
- reject already-assigned faces with `409 Conflict`

That behavior preserved a clean boundary for the next workflow slice: explicit correction and reassignment of already-labeled faces (Issue #43).

The system needs a deterministic way to fix incorrect labels without changing the initial-assignment contract and without prematurely implementing provenance-event persistence that belongs to Issue #44.

## Decision

Add a dedicated correction endpoint:

- `POST /api/v1/faces/{face_id}/corrections`

Request shape:

- `{ "person_id": "<id>" }`

Behavior:

- require the face to exist
- require the face to already be assigned (`faces.person_id IS NOT NULL`)
- require the target person to exist
- reject no-op corrections when the face is already assigned to the requested person
- update `faces.person_id` to the new person on success
- return `200 OK` with `{face_id, photo_id, previous_person_id, person_id}`

Failure semantics:

- `404 Not Found` for missing face or person
- `409 Conflict` for unassigned faces or no-op same-person corrections

## Consequences

- Initial assignment and correction are separate operations with separate intent.
- Callers can keep using assignment for unlabeled faces while using correction for reassignment.
- Responses include `previous_person_id`, giving clients explicit correction context.
- This slice intentionally keeps writing confined to `faces.person_id`; it does not create `face_labels` provenance events.
- Provenance and label-source persistence remains deferred to Issue #44.

## Alternatives Considered

- Allow in-place reassignment through `POST /assignments`
- Add correction by overloading existing assignment conflict behavior
- Start writing correction history directly to `face_labels` in this issue

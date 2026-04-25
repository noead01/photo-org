# ADR-0015: Introduce Face-To-Person Assignment API Workflow

- Status: Proposed
- Date: 2026-04-25

## Context

Phase 4 requires a concrete workflow to assign detected faces to existing people records.

Issue #41 introduced people-management APIs (`/api/v1/people`) and established person identities as the source of truth for user-managed names. The next delivery slice must make those identities usable by enabling assignment of an unlabeled face to a person.

The current schema already contains two related paths:

- `faces.person_id` (nullable)
- `face_labels` records with provenance fields

Later Phase 4 issues are explicitly reserved for:

- correction and reassignment workflows (#43)
- explicit provenance and assignment source behavior (#44)
- policy separation between human-confirmed and machine-applied labels (#45)

The assignment workflow for this slice therefore needs to be narrow, deterministic, and compatible with those upcoming behaviors without prematurely expanding into correction/provenance scope.

## Decision

Add a dedicated face-assignment API operation:

- `POST /api/v1/faces/{face_id}/assignments`

Request shape:

- `{ "person_id": "<id>" }`

Behavior:

- Assign only if the face exists and is currently unlabeled (`faces.person_id IS NULL`).
- Require the target person to exist in `people`.
- Persist the assignment by setting `faces.person_id`.
- Return `201 Created` with `{face_id, photo_id, person_id}` on success.
- Return `404 Not Found` when the face or person does not exist.
- Return `409 Conflict` when the face is already assigned.

To support caller workflows, include `face_id` in photo-detail face payloads (`GET /api/v1/photos/{photo_id}`) so clients can identify which detected face to assign.

Expose this workflow in OpenAPI under a dedicated `face-labeling` tag.

## Consequences

- Phase 4 has a concrete first assignment workflow that is usable in local development.
- Existing people records become actionable for labeling without requiring UI completion.
- Assignment semantics are intentionally conservative (no overwrite), reducing accidental relabeling and preserving space for explicit correction flows in #43.
- Persisting into `faces.person_id` keeps search and browse behavior compatible with current repository logic that already reads person links from `faces`.
- Provenance capture for assignments remains deferred to #44; this slice does not yet write `face_labels`.
- Future correction/reassignment work must define how `faces.person_id` and `face_labels` interact and whether historical label events are backfilled.

## Alternatives Considered

- Write assignments directly to `face_labels` in this slice
- Allow reassignment in-place within the same endpoint
- Infer assignment targets from display names instead of requiring `person_id`
- Delay API work until a web labeling UI exists

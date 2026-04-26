# ADR-0019: Enforce Faces-Person Foreign Key Integrity

- Status: Proposed
- Date: 2026-04-26

## Context

Issue #133 identifies a race between face assignment and person deletion. The API currently checks person existence before writing `faces.person_id`, but there is no database-level foreign key from `faces.person_id` to `people.person_id`.

Without a foreign key, concurrent deletes can leave `faces.person_id` pointing to a missing person record.

Phase 4 behavior already treats person deletion as conservative: deleting a referenced person returns `409 Conflict` rather than auto-unassigning or cascading.

## Decision

Add an explicit foreign key constraint from `faces.person_id` to `people.person_id` with:

- `ON DELETE RESTRICT`

Keep API contracts deterministic by mapping database integrity races to existing responses:

- assignment/correction race where target person disappears maps to `404 Person not found`
- delete race where new references appear maps to `409 Person is referenced by face or label data`

## Consequences

- `faces.person_id` can no longer persist dangling references when the database enforces foreign keys.
- Person deletion semantics remain conservative and aligned with existing Phase 4 API behavior.
- Service-layer existence checks remain useful for clear errors, while the FK provides last-line integrity under concurrency.

## Alternatives Considered

- `ON DELETE SET NULL` for `faces.person_id`
- no FK and rely only on application-layer existence checks
- cascading delete from `people` into `faces`

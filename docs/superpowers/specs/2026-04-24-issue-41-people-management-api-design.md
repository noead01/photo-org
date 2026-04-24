# Issue 41 People Management Model And API Design

Date: 2026-04-24
Issue: #41
Parent: #11 Phase 4: Face Labeling Workflow

## Summary

Implement the backend people-management slice for Phase 4. This adds API and service support for creating, listing, reading, renaming, and deleting people records without adding UI, face assignment, label correction, or recognition workflows.

The existing `people` table is the source of truth for this slice. It already provides the fields needed for a first people-management contract:

- `person_id`
- `display_name`
- `created_ts`
- `updated_ts`

No schema migration is expected for this issue unless implementation uncovers a missing contract.

## Goals

- expose a stable `/api/v1/people` API for backend clients
- support creating and managing people records before face-assignment workflows are built
- keep people management separate from face assignment, label correction, and recognition suggestions
- prevent deletion of people records that are already referenced by face or label data
- cover the API and service behavior with focused automated tests

## Non-Goals

- no web UI for people management
- no face-to-person assignment or correction workflow
- no validation-permission model
- no human-confirmed versus machine-applied label behavior beyond preserving existing schema compatibility
- no recognition suggestions, clustering, or threshold policy work
- no person search response changes beyond what existing search behavior already supports

## API Design

Add a new router mounted at `/api/v1/people`.

### Create Person

`POST /api/v1/people`

Request:

```json
{
  "display_name": "Jane Doe"
}
```

Behavior:

- trims surrounding whitespace from `display_name`
- rejects blank names with FastAPI/Pydantic validation
- allows duplicate display names
- creates a UUID-backed `person_id`
- sets `created_ts` and `updated_ts` to the same current timestamp
- returns `201 Created`

Response:

```json
{
  "person_id": "uuid",
  "display_name": "Jane Doe",
  "created_ts": "2026-04-24T12:00:00Z",
  "updated_ts": "2026-04-24T12:00:00Z"
}
```

### List People

`GET /api/v1/people`

Behavior:

- returns all people records
- orders deterministically by `display_name` then `person_id`
- does not include face counts or label metadata in this slice

### Get Person

`GET /api/v1/people/{person_id}`

Behavior:

- returns the person record when found
- returns `404 Not Found` when missing

### Update Person

`PATCH /api/v1/people/{person_id}`

Request:

```json
{
  "display_name": "Jane Smith"
}
```

Behavior:

- trims surrounding whitespace from `display_name`
- rejects blank names with FastAPI/Pydantic validation
- updates `display_name`
- refreshes `updated_ts`
- preserves `created_ts`
- returns `404 Not Found` when missing

### Delete Person

`DELETE /api/v1/people/{person_id}`

Behavior:

- deletes an unreferenced person and returns `204 No Content`
- returns `404 Not Found` when missing
- returns `409 Conflict` when the person is referenced by `faces.person_id` or `face_labels.person_id`

Deletion is intentionally conservative. A later label-correction workflow can decide how to reassign or remove dependent labels explicitly.

## Service Design

Create `app.services.people` as the domain-service boundary for people management. It should own:

- UUID generation
- timestamp assignment
- display-name normalization at the service boundary
- deterministic list ordering
- lookup and not-found behavior
- delete safety checks against `faces` and `face_labels`

Expected functions:

- `create_person(connection, *, display_name, now) -> dict`
- `list_people(connection) -> list[dict]`
- `get_person(connection, person_id) -> dict | None`
- `update_person(connection, *, person_id, display_name, now) -> dict`
- `delete_person(connection, person_id) -> None`

Use small exception classes for service-level failures:

- `PersonNotFoundError`
- `PersonInUseError`

The router should translate those exceptions into HTTP `404` and `409` responses.

## Validation

`display_name` is the only writable field in this slice.

Validation rules:

- strip surrounding whitespace
- require at least one non-whitespace character
- do not enforce uniqueness
- do not impose formatting rules beyond the non-empty requirement

Allowing duplicate display names is intentional. Names are not stable identities, and multiple people may share a display name. The stable identifier is `person_id`.

## Data Flow

Create and update calls flow from FastAPI request models into `app.services.people`, which mutates the existing `people` table through the request-scoped SQLAlchemy connection. The router commits successful mutations through the existing `get_db` session dependency pattern.

Read calls use the same service module and return Pydantic response models. No repository abstraction is needed for this narrow CRUD surface.

Delete calls first verify that the person exists, then check dependent references in `faces` and `face_labels`. If references exist, the service raises `PersonInUseError`; the router maps that to `409 Conflict`.

## Error Handling

- validation errors use FastAPI's default `422 Unprocessable Entity`
- missing people return `404 Not Found`
- referenced people return `409 Conflict`
- unexpected database errors are not caught by this slice and should surface through the normal API error path

## Testing Strategy

Follow TDD.

Add API-focused tests against SQLite migrations, matching existing FastAPI test patterns:

- creating a person trims `display_name` and returns `201`
- blank `display_name` is rejected
- listing people returns deterministic `display_name`, `person_id` order
- getting an existing person returns the record
- getting a missing person returns `404`
- updating a person changes `display_name`, refreshes `updated_ts`, and preserves `created_ts`
- updating a missing person returns `404`
- deleting an unreferenced person returns `204` and removes the row
- deleting a missing person returns `404`
- deleting a person referenced by `faces.person_id` returns `409`
- deleting a person referenced by `face_labels.person_id` returns `409`

Service-level tests may be added if edge cases become awkward to express through the API, but the API contract is the primary deliverable for this issue.

## Verification

Minimum verification:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -q
uv run python -m pytest apps/api/tests/test_openapi_docs.py -q
```

Before completion, run the broader API test suite if the implementation touches shared dependencies or OpenAPI metadata:

```bash
uv run python -m pytest apps/api/tests -q
```

## OpenAPI Documentation

Add the new router to `app.main` and include a `people` tag in the FastAPI metadata. Request and response models should include concise descriptions consistent with existing router style so the runtime OpenAPI schema documents the new API surface.

No checked-in generated OpenAPI artifact is expected because the repository currently generates `apps/api/.generated/openapi.yaml` on demand rather than tracking it.

## Future Work

This issue creates the people-management foundation for the remaining Phase 4 child issues:

- #42 face-to-person assignment workflow
- #43 face label correction and reassignment workflow
- #44 explicit label provenance and assignment source
- #45 separation of human-confirmed and machine-applied labels
- #46 permissions for face validation actions

Those workflows should consume this API and service boundary rather than adding parallel person-record mutation paths.

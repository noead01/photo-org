# Face False-Positive Dismissal Design

Date: 2026-05-06
Topic: Permanent dismissal of false-positive face detections from photo detail

## Summary

Allow an authorized human reviewer to permanently dismiss a detected face bounding box when it does not correspond to a real face.

The dismissal is:

- persistent
- available only from photo detail
- gated by the existing face-validation role
- not reversible in the product

Implementation should preserve the original detection record for auditability while removing the dismissed face from all active review and display surfaces.

## Goals

- Let a human discard a false-positive face detection from photo detail.
- Keep dismissed detections from reappearing in photo detail reads.
- Keep dismissed detections from reappearing in suggestion-review reads.
- Preserve audit context for why a detection stopped being active.
- Reuse existing role-gated face-review patterns and error handling.

## Non-Goals

- Adding a restore or undo workflow.
- Adding discard actions to the batch suggestions page.
- Deleting historical detection records outright.
- Solving detector drift across materially different future bounding boxes.

## Product Decisions (Validated)

- Dismissal is permanent from the product point of view.
- There is no restore action in this slice.
- Only users with the accepted `X-Face-Validation-Role` may dismiss a face.
- The action is exposed only on photo detail, not on `/suggestions`.
- Already-assigned faces cannot be dismissed as false positives.

## Current State Constraints

- `faces` is the durable record for detected face regions.
- Photo detail reads surface `faces` rows directly.
- Suggestion review reads also source active work from `faces`.
- There is no existing false-positive or dismissed state on `faces`.
- `face_labels` is used as a person-label provenance ledger, not as the source of detection lifecycle state.

## Recommended Approach

Store dismissal state directly on `faces` and treat only non-dismissed rows as active.

Why this approach:

- It preserves the original detection record instead of destroying it.
- It avoids overloading `face_labels` with non-label lifecycle state.
- It is smaller and clearer than introducing a separate review-status table.
- It naturally supports filtering dismissed faces out of all active read surfaces.

Rejected alternatives:

- Hard-delete the `faces` row.
  - Too destructive.
  - Loses auditability.
  - Makes later reasoning about detector behavior harder.
- Add a separate face review/status table.
  - More flexible, but unnecessarily heavy for a single permanent dismissal state.

## Data Model Design

Add dismissal fields directly to `faces`:

- `dismissed_ts TIMESTAMPTZ NULL`
- `dismissal_provenance JSON NULL`

Semantics:

- `dismissed_ts IS NULL` means the detection is active.
- `dismissed_ts IS NOT NULL` means the detection has been permanently dismissed as a false positive.
- `dismissal_provenance` records the action context for audit/debugging.

Proposed dismissal provenance payload:

```json
{
  "workflow": "face-labeling",
  "surface": "api",
  "action": "dismiss_false_positive"
}
```

Schema update policy:

- Update the initial Alembic revision directly.
- Keep the shared schema source aligned with the same fields and constraints.

Rationale:

- This repository is still evolving its initial schema directly in early-stage slices.
- No backward-compatibility migration flow is needed for this feature at the current stage.

## Write API Design

Add a role-gated endpoint on the existing face-labeling surface:

- `POST /api/v1/faces/{face_id}/dismissals`

Response shape:

- return the `face_id`
- return the owning `photo_id`
- return `dismissed_ts`

Success preconditions:

- face exists
- face is not already dismissed
- face is not assigned to a person

Successful behavior:

1. set `faces.dismissed_ts` to the current timestamp
2. set `faces.dismissal_provenance` to the dismissal provenance payload
3. delete any persisted `face_suggestions` rows for that `face_id`
4. commit the transaction

Error behavior:

- `403 Forbidden`
  - missing or unaccepted face-validation role
- `404 Not Found`
  - face does not exist
- `409 Conflict`
  - face is already assigned
  - face is already dismissed

Design note:

- Return conflicts for invalid state transitions instead of silently succeeding so the UI can surface state drift consistently with the existing assignment/correction endpoints.

## Read Behavior Design

Dismissed faces must be excluded from active read surfaces.

### Photo Detail

- `GET /api/v1/photos/{photo_id}` must omit dismissed faces from the `faces` list.
- Face-related metadata shown to the user should reflect active faces only.

Specifically:

- `metadata.faces_count` should count only non-dismissed faces
- overlay regions should only be built from non-dismissed faces
- people summaries should be derived from the filtered active face list as they are today

### Suggestions Review

- `GET /api/v1/suggestions/faces` must exclude dismissed faces.
- Any helper query that resolves “unassigned active suggestion work” must require `faces.dismissed_ts IS NULL`.

Rationale:

- Permanent dismissal should remove the false positive from all active human-review surfaces, not only from the page where it was dismissed.

## UI Design

Scope is limited to photo detail.

### Placement

Add a `Discard false positive` action for unlabeled faces in photo detail.

Recommended placement:

- alongside the existing unlabeled-face assignment controls
- not in the batch suggestions workflow
- not for already-labeled faces

### Interaction Behavior

On success, the client should update local detail state immediately so the dismissed face disappears without a full reload:

- remove the face from `detail.faces`
- update visible overlay boxes
- update unlabeled face assignment controls
- update visible people/face summary derived from current detail state

### Permissions and Errors

Use the same contributor header and overall error-handling style as other face-review actions.

Suggested message mapping:

- `403`: user lacks permission to discard faces
- `404`: face no longer exists
- `409`: face is already assigned or already dismissed
- network failure: generic discard failure message

## State and Data Flow

1. User opens photo detail.
2. UI loads active faces from `GET /api/v1/photos/{photo_id}`.
3. User triggers `Discard false positive` for an unlabeled face.
4. UI calls `POST /api/v1/faces/{face_id}/dismissals` with the face-validation role header.
5. API validates state and persists dismissal on `faces`.
6. API deletes any stale `face_suggestions` rows for that face.
7. UI removes the face from local state after success.
8. Subsequent photo-detail and suggestions-review reads no longer include that face.

## Edge Conditions

- Dismissing an already-assigned face is rejected.
- Dismissing an already-dismissed face is rejected.
- If a later ingest rerun touches the same face record, the face remains dismissed because the row still exists.
- If detector changes yield a materially different bounding box and therefore a different `face_id`, that new detection may appear again as new review work.

This last case is acceptable in this slice because detector-identity reconciliation is a separate concern from permanent dismissal of an existing detection record.

## Testing Strategy

### Backend

Add tests for:

- successful dismissal of an unassigned face
- rejection when role header is missing
- rejection when role header is unaccepted
- `404` for unknown face
- `409` for already-assigned face
- `409` for already-dismissed face
- persisted suggestion rows are removed for dismissed faces
- photo detail omits dismissed faces
- photo detail `metadata.faces_count` reflects active faces only
- suggestions review omits dismissed faces

### Frontend

Add tests for:

- discard action is shown for an unlabeled face in photo detail
- discard action is not shown for labeled faces
- successful dismiss removes the face from the overlay immediately
- successful dismiss removes the face from assignment controls immediately
- permission/conflict failures surface the correct error message

## Implementation Notes

- Keep dismissal state on `faces`; do not extend `face_labels` for this feature.
- Reuse existing face-review router/service structure instead of creating a separate subsystem.
- Apply the active-face filter consistently in repository and suggestion-review queries to avoid split-brain behavior between surfaces.

## Open Follow-Ups

- If future product work needs reviewer history or restore behavior, revisit whether `faces` state is still sufficient or whether a dedicated review-event model is warranted.
- If detector drift becomes noisy in practice, consider a later feature for suppressing semantically similar future detections rather than only the exact historical `face_id`.

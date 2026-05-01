# Issue #183 Design: Face-to-Person Assignment Interactions In Photo Detail

## Summary

Implement assignment interactions for unlabeled faces directly in photo detail with deterministic inline feedback and automatic advance to the next unlabeled face after successful assignment.

## Scope

- Expose assignment action for eligible face regions (faces with `person_id === null`).
- Provide person selection interaction from existing people records.
- Submit assignment via backend assignment API and represent success/failure deterministically.
- Refresh photo detail assignment state in-place after success.

## Non-Goals

- Correction/reassignment for already-labeled faces.
- Suggestion confidence, candidate ranking, or review-needed workflows.
- Global permission/session framework beyond required assignment header for this slice.

## UX Decisions (Validated)

- Assignment interaction uses dropdown selection with immediate submit (no separate confirm button).
- Picker shows person `display_name` only.
- On success, workflow auto-advances to next unlabeled face in stable face order.
- Errors are shown inline on the active face assignment row.

## Architecture

### Parent Page: `PhotoDetailRoutePage`

- Remains source of truth for loaded photo detail payload.
- Loads people directory for assignment options using `GET /api/v1/people`.
- Hosts assignment success callback that updates local `detail.faces[].person_id` without full-page reload.
- Recomputes derived display state from updated face assignments.

### New Child Component: `FaceAssignmentControls`

Responsibilities:

- Receives face list + people directory options from parent.
- Computes ordered unlabeled-face queue.
- Tracks active unlabeled face, submit-in-flight state, and inline error message.
- Triggers assignment POST on person selection.
- Calls parent success callback and advances to next unlabeled face.

This keeps new behavior isolated from existing photo metadata/rendering concerns while avoiding speculative abstraction for future correction workflow.

## API Contract

### People directory

- `GET /api/v1/people`
- Used to populate selectable options.
- Label shown in UI: `display_name`.
- Submitted value: `person_id`.

### Face assignment

- `POST /api/v1/faces/{face_id}/assignments`
- Headers:
  - `Content-Type: application/json`
  - `X-Face-Validation-Role: contributor`
- Body:

```json
{
  "person_id": "person-123"
}
```

- Success response: `201` with `{ face_id, photo_id, person_id }`.

## Deterministic Feedback Behavior

### Success

- Clear inline error.
- Update face assignment state in parent detail model.
- Advance to next unlabeled face automatically.
- If no unlabeled faces remain, show explicit completion state (`All visible faces assigned.`).

### Failure mapping (inline)

- `403`: `You do not have permission to assign faces.`
- `404`: API detail if present, else `Face or person no longer exists.`
- `409`: API detail if present, else `Face is already assigned.`
- Other non-OK: `Assignment request failed (500).` (status code interpolated at runtime)
- Network/exception: `Could not assign face.`

### Interaction constraints

- Disable active picker while request is in flight.
- Keep workflow single-threaded: only active unlabeled face is interactive.
- Preserve stable face traversal order using existing `detail.faces` order.

## Testing Strategy

Add/extend UI tests to verify:

- people directory fetch for assignment options;
- assignment request payload + required header;
- success updates face label state and advances active face;
- completion state after final unlabeled face assignment;
- deterministic inline errors for `403/404/409/500` and network failure;
- disabled state while assignment request is pending.

## Risks And Mitigations

- Risk: detail page state drift after assignment.
  - Mitigation: canonical in-memory update path in parent from assignment response.
- Risk: person display-name ambiguity.
  - Mitigation: display-only names but submit by `person_id` value.
- Risk: unauthorized environments.
  - Mitigation: deterministic `403` inline error; no silent failure.

## Acceptance Criteria Mapping

- Unlabeled faces can be assigned from UI: covered by active unlabeled-face picker and POST flow.
- Assignment success/failure represented deterministically: covered by status mapping and inline feedback.
- Detail UI reflects new assignment state after success: covered by parent state update + auto-advance.

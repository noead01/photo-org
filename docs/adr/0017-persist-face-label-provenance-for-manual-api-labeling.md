# ADR-0017: Persist Face Label Provenance For Manual API Labeling

- Status: Proposed
- Date: 2026-04-26

## Context

Issue #42 introduced conservative face assignment and Issue #43 added explicit correction and reassignment. Both slices intentionally only updated `faces.person_id` and deferred provenance writes to Issue #44.

The schema already includes a `face_labels` table with provenance-oriented fields (`label_source`, `confidence`, `model_version`, `provenance`). Without writing label events, manual labeling actions are not audit-friendly and later policy work (#45) has no persisted source trail to enforce.

## Decision

Persist one `face_labels` event row for each successful manual API labeling action:

- assignment endpoint (`POST /api/v1/faces/{face_id}/assignments`)
- correction endpoint (`POST /api/v1/faces/{face_id}/corrections`)

Event persistence rules:

- continue using `faces.person_id` as the current resolved label
- append one `face_labels` row after each successful write
- set `label_source = "manual"` for these API actions
- set `confidence` and `model_version` to `NULL` for manual writes
- persist `provenance` JSON with operation metadata (`workflow`, `surface`, `action`)
- include `previous_person_id` in correction provenance

## Consequences

- Manual labeling operations now produce durable provenance events.
- Reassignment history is captured as append-only events in `face_labels`.
- Existing assignment and correction API request/response contracts remain stable.
- Issue #45 can enforce policy distinctions (human-confirmed vs machine-applied) on top of persisted source metadata rather than inferred behavior.

## Alternatives Considered

- Keep provenance implicit in endpoint behavior and avoid writing `face_labels`
- Replace `faces.person_id` with `face_labels` as the only source of current truth in this slice
- Add machine-label policy enforcement in this issue

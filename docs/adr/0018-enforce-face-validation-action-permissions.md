# ADR-0018: Enforce Face Validation Action Permissions

- Status: Proposed
- Date: 2026-04-26

## Context

Issue #42 introduced manual face-to-person assignment and Issue #43 added explicit correction and reassignment. Issue #44 then persisted manual labeling provenance in `face_labels`, and Issue #45 enforced source separation for human-confirmed versus machine-applied labels.

Those workflows can currently be invoked by any API caller because there is no permission gate on face-validation mutation endpoints. That leaves no way to enforce the Phase 4 requirement that only authorized contributors can confirm or correct face labels.

## Decision

Require an explicit role header for face-validation mutation endpoints:

- `POST /api/v1/faces/{face_id}/assignments`
- `POST /api/v1/faces/{face_id}/corrections`

Authorization contract:

- request header: `X-Face-Validation-Role`
- accepted values: `contributor`, `admin`
- missing or unrecognized values return `403 Forbidden` with `{"detail":"Face validation role required"}`

This issue intentionally uses a lightweight header contract so the API can enforce authorization boundaries now without blocking on a broader identity system rollout.

## Consequences

- Face-validation mutations are now restricted to authorized callers.
- UI, CLI, and test clients must include an accepted face-validation role header when issuing assignment or correction actions.
- OpenAPI now documents both the required permission header and `403` permission-failure responses for these endpoints.
- Future authentication work can map real user identity claims to the same role gate without changing endpoint paths.

## Alternatives Considered

- Leave face-validation endpoints open to all callers until a full auth stack is introduced.
- Restrict validation actions to only one role (for example, `admin`) and defer contributor access.
- Add dedicated user and role persistence in this issue rather than using an explicit request-role contract.

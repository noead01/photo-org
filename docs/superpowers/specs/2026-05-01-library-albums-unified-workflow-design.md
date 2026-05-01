# Unified Library + Shareable Albums + Export Workflow Design

Date: 2026-05-01

## Summary

Unify browsing and filtering into a single Library workspace, add shareable in-app albums backed by database photo references, and provide album export to the user's local filesystem.

This design shifts albums from "copied photo bundles" to first-class collaborative entities while preserving an explicit export action for external use.

## Goals

- Combine Browse and Search into one visual-first Library screen.
- Keep filtering/search controls and photo selection on the same screen.
- Allow direct face assignment/confirmation from the Library workflow.
- Add shareable albums as database entities that reference photos.
- Enable export of album photos to the user's local filesystem.

## Non-Goals

- Public or unauthenticated share links.
- Cross-tenant sharing.
- Changing face-recognition model behavior.
- Binary asset deduplication redesign.

## User Journeys Covered

1. As a user, I can visually browse photos with key attributes and select them.
2. As a user, I can assign a person's name to detected faces from the active selection workflow.
3. As a user, I can confirm or correct machine-assigned face labels with provenance visibility.
4. As a user, I can save selected/filtered photos to an album and later export that album externally.

## IA And Navigation

### Primary routes

- `Library` (new primary working route)
- `Albums` (new route)
- `Photo Detail` (retained for deep inspection)
- `Labeling` (people management retained)

### Route migration

- Default app landing route becomes `Library`.
- Existing `/browse` and `/search` are preserved as temporary redirects into `Library` URL-state equivalents during migration.

## Approaches Considered

1. Keep separate Browse and Search routes, improve both.
2. Merge into a unified Library route with persistent filters and visual results. (Recommended)
3. Make Albums the first-class working route and browse from album context.

## Decision

Adopt Approach 2.

Reasoning: it aligns with the core use case (visual select + filter + act) and avoids context switching while still supporting deep detail and collaboration flows.

## UX Design

### Library workspace

- Always visual result grid.
- Persistent filter/search controls in the same screen.
- Selection affordances:
  - single select
  - multi-select
  - select current page
  - select all filtered results
- Action bar appears when selection exists.

### Face workflow in Library

- Face regions shown in preview/quick panel.
- Unassigned faces allow direct assignment.
- Machine-labeled faces allow `Confirm` or `Correct`.
- Provenance badges remain visible.
- New face-state filter affordances:
  - `Unassigned faces`
  - `Machine-labeled, unconfirmed`

### Album workflow

- `Add to album` from selection action bar.
- User can choose existing album or create new album inline.
- Album detail view lists referenced photos and collaborator access.

### Sharing model

Authenticated in-app sharing only.

- Owner grants access to specific app users.
- Roles:
  - `viewer`: read album
  - `editor`: add/remove album photos and manage working content

### Export workflow

Export is an album action, not a replacement for album storage.

- Action: `Export album to...`
- Preferred: browser directory picker and direct local-folder write when supported.
- Fallback: ZIP download artifact for browsers without writable directory APIs.
- Completion summary includes exported/skipped counts and reasons.

## Data Model

### `albums`

- `album_id` (PK)
- `name`
- `owner_user_id`
- `created_ts`
- `updated_ts`

### `album_items`

- `album_id` (FK -> albums)
- `photo_id` (FK -> photos)
- `added_by_user_id`
- `added_ts`
- Unique: `(album_id, photo_id)`

### `album_shares`

- `album_id` (FK -> albums)
- `user_id`
- `role` (`viewer` | `editor`)
- `granted_by_user_id`
- `granted_ts`
- Unique: `(album_id, user_id)`

## API Surface

### Albums

- `POST /api/v1/albums` create album
- `GET /api/v1/albums` list owned + shared albums
- `GET /api/v1/albums/{album_id}` album metadata + paged items
- `PATCH /api/v1/albums/{album_id}` rename/update metadata
- `DELETE /api/v1/albums/{album_id}` delete album

### Album items

- `POST /api/v1/albums/{album_id}/items` add photo references (single/batch)
- `DELETE /api/v1/albums/{album_id}/items/{photo_id}` remove reference

### Sharing

- `POST /api/v1/albums/{album_id}/shares` grant access to user
- `PATCH /api/v1/albums/{album_id}/shares/{user_id}` change role
- `DELETE /api/v1/albums/{album_id}/shares/{user_id}` revoke access

### Export

- `POST /api/v1/albums/{album_id}/exports` create export job manifest
- `GET /api/v1/albums/{album_id}/exports/{export_id}` poll status and retrieve artifact metadata (fallback ZIP flow)

## Permission Rules

- Owner: full album and share management.
- Editor: add/remove album items, trigger export.
- Viewer: read-only access; export allowed unless policy later restricts it.

## Error Handling

- Duplicate album item add returns deterministic conflict response; UI reports "already in album" count.
- Share grant to unknown user returns validation error.
- Export failures report per-photo reason categories (missing original, access denied, read failure).
- Directory-write capability unavailable triggers explicit fallback to ZIP download flow.

## Acceptance Criteria

1. Library route provides both visual browsing and filtering/search on one screen.
2. Library face workflows support assignment and machine-label confirm/correct without mandatory navigation to Photo Detail.
3. Users can save selected or filtered photos to albums backed by DB references.
4. Albums can be shared with authenticated app users and role-enforced access works.
5. Album export supports local filesystem destination via directory picker where available, with ZIP fallback where not.
6. Export completion reports include deterministic success/skip counts and skip reasons.

## Testing Strategy

### UI

- Library renders visual cards with active filter state and selection actions.
- Add-to-album flows for selected subset and select-all-filtered mode.
- Face-state filter behavior (`unassigned`, `unconfirmed machine labels`).
- Share panel role changes and permission-gated controls.
- Export capability detection and ZIP fallback UX.

### API

- CRUD and list coverage for albums.
- Duplicate reference conflict behavior.
- Access control matrix (owner/editor/viewer/non-member).
- Export job lifecycle and result reporting contract.

### E2E journeys

- Build album from filtered Library results.
- Share album with second authenticated user and verify permissions.
- Export shared album to local destination path flow (capability-aware).

## Risks And Mitigations

- Browser API fragmentation for local writes.
  - Mitigation: explicit capability check + ZIP fallback.
- Selection scale for "all filtered" with large result sets.
  - Mitigation: server-side selection token/manifest semantics, not client-only ID accumulation.
- Permission drift between UI and API.
  - Mitigation: server-authoritative checks and explicit UI gating from role payload.

## Migration Notes

- Existing Browse/Search behaviors become internal modules inside Library.
- Keep legacy routes as redirects short-term to preserve deep links.
- Existing Photo Detail face controls remain valid and reused for deep inspection until full Library quick-panel parity is complete.

## Out Of Scope Follow-Ups

- Public share links.
- Time-bound share invitations.
- Collaborative album activity feed.

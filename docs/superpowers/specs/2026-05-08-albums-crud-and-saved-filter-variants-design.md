# Albums CRUD + Saved Filter Variants Design

Date: 2026-05-08

## Summary

Add a first-class `Albums` route with CRUD operations and album membership management, while supporting two album variants:

- `Editable`: explicit photo membership that users can add/remove directly.
- `Saved Filter`: rule-based membership derived from Library filters; content updates dynamically as data changes.

The Library `Add to album` action becomes a modal with type selection (`Editable` vs `Saved Filter`) and inline explainer affordance.

## Goals

- Provide top-level Albums navigation and route (`/albums`).
- Support album CRUD (create, list, rename, delete).
- Support membership management for editable albums (add uniquely, remove directly).
- Support saved-filter albums powered by the full Library filter contract.
- Allow Library filtering by albums as a multi-select OR facet.
- Replace `window.prompt` add-to-album with an explicit, accessible modal flow.

## Non-Goals

- Sharing and collaborator role management.
- Public links or cross-tenant album access.
- Overwriting existing saved-filter albums from Add-to-Album flow.

## Product Decisions

1. Albums have two user-visible variants: `Editable` and `Saved Filter`.
2. `Saved Filter` in Add-to-Album supports create-new only.
3. Album names are unique per user, case-insensitive.
4. If adding to an editable album, selected photos are added uniquely; existing members remain unchanged.
5. Library album facet is multi-select with OR semantics (photos in any selected album).

## Data Model

Use distinct entities for editable membership and saved filters.

### `albums`

- `album_id` (PK)
- `owner_user_id`
- `name`
- `kind` (`editable` | `saved_filter`)
- `created_ts`
- `updated_ts`
- Unique constraint: `(owner_user_id, lower(name))` (or equivalent case-insensitive uniqueness strategy)

### `editable_album_items`

- `album_id` (FK -> `albums`)
- `photo_id` (FK -> `photos`)
- `added_by_user_id`
- `added_ts`
- Unique: `(album_id, photo_id)`

### `saved_filter_album_rules`

- `album_id` (FK -> `albums`, unique)
- `filter_json` (validated Library filter payload)
- `updated_ts`

## API Contract

Unified album endpoints with behavior conditioned by `kind`.

### CRUD

- `POST /api/v1/albums`
  - accepts `name`, `kind`
  - for `saved_filter`, requires `filter_json`
- `GET /api/v1/albums`
  - returns owned albums with counts/metadata
- `GET /api/v1/albums/{album_id}`
  - editable: returns explicit members (paged)
  - saved_filter: returns resolved members (paged) computed from `filter_json`
- `PATCH /api/v1/albums/{album_id}`
  - rename for both kinds
  - optional `filter_json` update for `saved_filter` via albums route
- `DELETE /api/v1/albums/{album_id}`

### Membership

- `POST /api/v1/albums/{album_id}/items`
  - allowed only for `editable`
  - adds photo IDs uniquely
  - response includes `added_photo_ids`, `duplicate_photo_ids`, `missing_photo_ids`
- `DELETE /api/v1/albums/{album_id}/items/{photo_id}`
  - allowed only for `editable`

### Search Integration

- Extend search filter contract with `album_ids: string[]`.
- Behavior: OR semantics across selected album IDs.
- Add album facet counts to search response.

## Validation + Error Handling

- Duplicate album name for owner returns `409 Conflict` with message:
  - `Album name already exists. Choose a different name.`
- Editable membership operations on non-editable albums return `409 Conflict` with deterministic detail.
- Empty or invalid IDs return `422`.
- Album not found returns `404`.
- Add operation remains idempotent for duplicate members (reported, not fatal).

## UI/UX

## Albums Route

- New top-level nav item `Albums`.
- `/albums` shows:
  - album list (name, type badge, count, last updated)
  - create action
  - rename/delete actions
  - detail panel/grid for selected album contents
- Detail behavior:
  - editable: remove controls on photos
  - saved_filter: read-only results with explanation that contents are rule-derived

## Library Add-to-Album Modal

- Replaces prompt-based flow.
- Radio selection:
  - `Editable`
  - `Saved Filter`
- Include `(i)` info affordance with accessible explanatory content:
  - Editable: explicit membership, direct add/remove.
  - Saved Filter: dynamic rule-based membership.
- Editable mode:
  - choose existing editable album or create new editable album
  - adds current selection scope photos uniquely
- Saved Filter mode:
  - create new saved-filter album only
  - persists current full Library filter contract as `filter_json`
  - if name exists, keep modal open and show inline validation error

## Testing Strategy

### API

- CRUD coverage for both kinds.
- Name uniqueness conflict coverage.
- Editable add/remove semantics (including duplicates/missing).
- Guard rails preventing membership mutation on saved-filter albums.
- Saved-filter resolution uses full filter contract.
- Search filter `album_ids` OR semantics + facet counts.

### UI

- Albums route list/detail rendering for both kinds.
- Create/rename/delete flows.
- Add-to-album modal:
  - type switching
  - info affordance visibility/accessibility
  - editable existing/new behavior
  - saved-filter create-only behavior and conflict messaging
- Remove-from-editable-album interactions.
- Library album facet multi-select OR behavior.

## Migration Notes

- Introduce new tables/entities for editable membership and saved-filter rules.
- Migrate existing `album_items` data into `editable_album_items` with `albums.kind = editable`.
- Backfill `kind = editable` for existing albums unless explicitly converted through future migration tooling.

## Risks And Mitigations

- Risk: Filter schema drift between Library and saved-filter resolver.
  - Mitigation: shared validation/parsing utilities and contract tests.
- Risk: Confusion between editable and saved-filter semantics.
  - Mitigation: explicit type badges, `(i)` explainer, and read-only visual treatment for saved-filter results.

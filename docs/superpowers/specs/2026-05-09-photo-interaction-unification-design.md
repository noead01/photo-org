# Photo Interaction Unification Design

## Summary

Unify photo, face, metadata, selection, and album interactions across the UI through reusable concepts and composable components. Library, Suggestions, Albums, and Photo Detail should present photos differently when their workflow requires it, but the underlying interaction model should be consistent: photos are selectable, thumbnails open detail, face controls open the same assignment workflow, metadata opens the same retargetable flyout, and album assignment consumes photo selection without interfering with face-review selection.

## Goals

- Provide a single interaction model for photos across grid cards, Suggestions, Albums, and Photo Detail.
- Reify shared UI concepts: photo, face, face assignment, photo selection, face review selection, metadata/details, album target, and album assignment.
- Preserve performance in 100+ photo grids by using thumbnails and demand-loading full details only when the user asks.
- Keep photo selection stable while users open metadata, face assignment, album actions, or Photo Detail.
- Keep Suggestions as a specialized batch face-review screen while still exposing shared photo functionality.

## Non-Goals

- Replacing the Suggestions batch-review workflow with a general photo grid.
- Loading original images in normal grid contexts.
- Redesigning backend face assignment or album APIs beyond any payload support needed by the shared UI contracts.
- Implementing the feature in this spec. This document defines the target design for a later implementation plan.

## Validated UX Decisions

- Thumbnail click opens Photo Detail.
- Photo selection is an explicit control, separate from thumbnail navigation and face actions.
- Photo Detail exposes the same selected/unselected photo state as grids.
- Face boxes are off by default on normal grids and controlled by a visible toggle.
- Suggestions opts into face boxes on by default.
- Suggestions keeps photo selection separate from selected faces for batch review.
- Bulk actions in Suggestions apply to faces only unless they are album/photo actions; album assignment consumes photo selection only.
- Face assignment uses a centered modal with its own thumbnail view and selected face context.
- Metadata and EXIF details use a non-modal flyout that can retarget to another photo without closing.
- The active metadata target is indicated by a distinct frame on the source photo surface and confirmed in the flyout header.
- Photo Detail remains the explicit full/original-view route and may continue loading original content automatically.

## Architecture

### Route Owners

Route pages continue to own route-specific concerns:

- Library: search state, filters, pagination, normal grid defaults, library action bar.
- Suggestions: batch face-review state, suggestion filters, face-review bulk actions, face boxes on by default.
- Albums: album list/detail context, album membership views, album-specific photo actions.
- Photo Detail: original image loading, detail route navigation, full photo inspection.

Routes should not independently implement photo selection, face overlays, metadata targeting, album assignment controls, or face assignment UX when those behaviors are shared.

### Shared Composition Layer

Introduce a shared photo interaction layer that route pages compose:

- `PhotoInteractionProvider`: owns or bridges cross-screen interaction state for selected photos, active metadata target, active face assignment target, face-box visibility, and active source-surface framing.
- `PhotoSurface`: renders one photo in thumbnail or original mode with consistent selection, metadata, face overlay, and detail navigation affordances.
- `PhotoGridSurface`: arranges `PhotoSurface` items for grid-style routes while preserving screen-specific density and defaults.
- `PhotoSelectionControls`: exposes selected/page/all-filtered selection scope and clear/toggle behavior.
- `FaceOverlayLayer`: renders face boxes from shared face-region data and delegates clicks to shared face actions.
- `PhotoActionBar`: hosts shared photo-level actions such as metadata, open detail, album assignment, and screen-specific extension points.
- `AlbumActionSurface`: provides reusable album assignment actions for selected photos.

The shared layer should adapt to each route through props and route-owned defaults rather than hidden global behavior.

### Shared Inspectors

Shared inspectors are invoked from any route without resetting photo or face-review state:

- `FaceAssignmentModal`: centered modal, thumbnail-first, supports assign known person, create person, mark unknown human, discard false positive, confirm machine label, and correct existing assignments where eligible.
- `PhotoMetadataFlyout`: non-modal flyout, shows summary fields immediately when available, demand-loads full detail/EXIF for the active target, and can retarget while open.
- Photo Detail link/navigation: explicit route transition to original/full view, carrying photo selection state and return focus context.

## Data Contracts

Route API payloads should be adapted into shared contracts before reaching reusable components.

### Photo And Face Contracts

- `PhotoSummary`: photo id, path/title, thumbnail, original availability summary, captured timestamp, file size, people/faces summary, and optional album context.
- `PhotoMedia`: thumbnail media for grids and modals, plus explicit original-image intent for Photo Detail.
- `PhotoFace`: face id, person id, bbox values, bbox coordinate space, label source, confidence, model version, provenance, suggestions, and action eligibility.
- `FaceRegion`: rendered percentage coordinates derived from `PhotoFace` and thumbnail coordinate space.

### Selection Contracts

- `PhotoSelectionState`: selected photo ids, selection scope (`selected`, `page`, `allFiltered`), and active filtered fingerprint.
- `FaceReviewSelectionState`: Suggestions-only selected face ids for batch review.
- `PhotoInspectorState`: active metadata photo id, active face assignment target, face-box visibility, and active source surface id used for framing.

Photo selection and face-review selection are intentionally separate. A selected photo is an album/photo-action target; a selected face is a Suggestions batch-review target.

### Album Contracts

- `AlbumTarget`: album id, name, kind, and whether the album accepts manual photo additions.
- `AlbumAssignmentState`: selected photo ids, active selection scope, in-flight add/remove/export state, and result summary.
- `PhotoAlbumMembership`: optional per-photo album ids or membership hints when a screen needs to show current-album membership.

Album assignment must be available from screens that support photo selection, including Suggestions. It must not consume or mutate selected face ids.

## Interaction Behavior

### Photo Surface

- Clicking the image/thumbnail opens Photo Detail.
- Toggling the photo checkbox changes photo selection only.
- Opening metadata, face assignment, or album actions must not clear photo selection.
- A selected photo remains selected when opening Photo Detail and returning to the grid.
- Photo Detail includes the same selected/unselected control as grid surfaces.

### Face Boxes

- Normal grids default face boxes off.
- Suggestions defaults face boxes on.
- The face-box toggle is screen-level where multiple photos are shown.
- Face boxes are rendered from thumbnail coordinate space in grids and from the active image coordinate space in Photo Detail when available.
- Clicking a face control opens `FaceAssignmentModal`; clicking the thumbnail behind it still follows the normal open-detail behavior.

### Face Assignment Modal

- The modal is centered and modal, independent of the underlying card layout.
- The modal shows the full thumbnail view of the photo and highlights or identifies the active face.
- It uses thumbnail media for grid and Suggestions invocation.
- It fetches people/candidates only when opened and only when missing from the invoking payload.
- It supports existing face-labeling workflows through shared API/state helpers.
- Closing the modal leaves photo selection and Suggestions face-review selection unchanged.

### Metadata Flyout

- The flyout is non-modal and can remain open while the user targets another photo.
- The source `PhotoSurface` for the active metadata target receives a distinct active-inspector frame.
- The flyout header repeats the photo identity and thumbnail so the target is unambiguous.
- If the active target leaves the current grid due to filtering or pagination, the flyout closes unless the route explicitly retargets it.

### Album Assignment

- Album actions operate on `PhotoSelectionState`.
- Routes can expose add-to-existing-album and create-and-add workflows through `AlbumActionSurface`.
- Suggestions shows album/photo actions separately from face-review bulk actions.
- Album results report added, duplicate/already-present, missing/unavailable, and failed counts where available.

## Performance And Loading

- Grid-style screens use list/search payloads and thumbnails only.
- No original image content is fetched in Library, Suggestions, Albums, or album detail grids.
- Face assignment from grids uses thumbnail plus face bbox/suggestion data in the common case.
- Full photo detail/EXIF is demand-loaded only for the active metadata target.
- Photo Detail remains the explicit full-view surface and may continue loading original images automatically with thumbnail fallback.
- Avoid per-card detail requests in 100+ photo grids.
- Face region construction must stay pure and cheap; candidate/person lookups happen on inspector open, not during grid render.
- Backend list/search payloads may need to include enough face and thumbnail metadata to support the shared thumbnail-first interactions without full detail fetches.

## Error Handling And State Integrity

- Inspector actions never clear or mutate photo selection unless the action is explicitly about selection.
- Face assignment, correction, unknown-human, false-positive, and confirmation actions update local face state only after API success.
- Face dismissal closes the modal for that face and updates the local face list; it does not affect photo selection.
- Metadata load errors stay scoped to the flyout and provide retry without disrupting the grid.
- Album assignment reports partial success clearly and keeps selection available for retry unless the user clears it.
- Stale or missing face/photo data should show scoped retry/error states instead of closing unrelated UI.

## Testing Strategy

### Unit Tests

- Adapters from route payloads to `PhotoSummary`, `PhotoFace`, album targets, and selection contracts.
- Photo selection reducer and route serialization.
- Face review selection reducer for Suggestions.
- Metadata target reducer.
- Album assignment state/result formatting.
- Face overlay region construction and coordinate-space handling.

### Component Tests

- `PhotoSurface`: thumbnail click opens detail; checkbox toggles selection; metadata and face actions do not toggle/open the wrong target.
- `FaceOverlayLayer`: default visibility, keyboard behavior, and face action delegation.
- `FaceAssignmentModal`: thumbnail context, person assignment, create person, unknown, false positive, confirmation, correction, close behavior.
- `PhotoMetadataFlyout`: retargeting, active-source frame, staged detail loading, close behavior.
- `AlbumActionSurface`: add to album, create and add, partial result messaging, disabled/in-flight states.
- Composed grid behavior for normal grids and Suggestions defaults.

### Route Integration Tests

- Library, Albums, Suggestions, and Photo Detail share photo selection behavior.
- Selection survives metadata flyout, face assignment modal, and Photo Detail navigation.
- Face boxes default off in normal grids and on in Suggestions.
- Suggestions keeps photo selection distinct from selected faces.
- Selected Suggestions photos can be added to albums without changing selected faces.
- Grid interactions do not fetch original images.
- Photo Detail still loads original images automatically.

### E2E Journey

Add a journey that starts in Suggestions, selects faces for review, separately selects photos for album assignment, opens metadata, opens face assignment, navigates to Photo Detail, and verifies these states remain independent.

## Risks And Mitigations

- Risk: A shared layer becomes too generic and hard to use.
  - Mitigation: Model only validated concepts and keep route defaults explicit through props.
- Risk: Suggestions behavior is flattened into generic grid behavior.
  - Mitigation: Keep Suggestions as a route-owned batch-review workflow with shared photo affordances composed into it.
- Risk: Performance regression from detail fetches in grids.
  - Mitigation: Make thumbnail-first behavior part of the shared contract and test that grid interactions do not fetch originals.
- Risk: Selection state conflicts between photo and face actions.
  - Mitigation: Separate `PhotoSelectionState` and `FaceReviewSelectionState` and test Suggestions interactions directly.
- Risk: Active metadata target is ambiguous.
  - Mitigation: Frame the active source surface and repeat identity in the flyout header.

## Acceptance Criteria

- Shared components exist for photo surfaces, face overlays, metadata flyout, face assignment modal, and album assignment controls.
- Library, Suggestions, Albums, and Photo Detail consume shared photo interaction concepts instead of route-specific duplicates.
- Photo selection persists across inspectors and Photo Detail navigation.
- Suggestions has independent photo selection and face-review selection.
- Album assignment can be launched from Suggestions photo selection.
- Metadata flyout can retarget while open and clearly frames the active source photo.
- Normal grids stay thumbnail-first and do not fetch original images.
- Photo Detail remains the explicit original/full-view surface.

# Issue #185: Label Provenance Indicators And Detail Affordances Design

Date: 2026-05-01
Parent: #161
Issue: #185

## Summary

Expose face-label provenance in photo-detail labeling surfaces so users can quickly distinguish human-confirmed versus machine-generated labeling and inspect source metadata without leaving the current workflow.

## Why This Matters

Face labeling accuracy depends on user trust and clear provenance visibility. If provenance is hidden or ambiguous, users cannot confidently decide when to keep, correct, or challenge existing labels.

## Scope

- Add provenance payload fields to photo detail face objects.
- Show compact provenance badges in:
  - labeled face rows in correction UI
  - face overlay boxes in preview
- Provide inline expandable provenance details in correction UI.
- Define deterministic fallback behavior for missing or legacy provenance data.
- Add API and UI tests for provenance rendering and fallback behavior.

## Non-Goals

- Any database schema change.
- Any provenance write-path change in assignment/correction APIs.
- Permission policy changes.

## Data Contract

### API shape change

Extend each face item in photo detail response with:

- `label_source: "human_confirmed" | "machine_applied" | "machine_suggested" | null`
- `confidence: number | null`
- `model_version: string | null`
- `provenance: Record<string, unknown> | null`
- `label_recorded_ts: string | null`

### Mapping logic

- For each face with `person_id != null`, resolve latest matching `face_labels` row for:
  - same `face_id`
  - same `person_id`
  - newest by timestamp (created/updated ordering)
- Map row fields into the photo detail face payload.
- For faces with no matching label row (legacy/missing provenance), return explicit `null` values for all provenance fields.
- For unlabeled faces (`person_id == null`), return explicit `null` values for all provenance fields.

## UX Design

### Badge system (language-independent symbols)

- `👤` for `human_confirmed`
- `🤖` for `machine_applied`
- `💡` for `machine_suggested`
- `❓` for missing provenance

Each badge has an accessible text label for assistive tech and deterministic automation assertions.

### Labeled-face row behavior

- Render a provenance badge next to each labeled face entry in the correction list.
- Badge acts as toggle button (`aria-expanded`) for inline provenance details.
- Single-expanded-row behavior: opening one row collapses any previously open row.

### Overlay behavior

- Render compact provenance badge inside each face overlay with existing overlay box geometry.
- Tapping/clicking overlay badge expands the matching inline details row in correction UI.
- Overlay remains compact and non-blocking on mobile.

### Inline details panel fields

For expanded row, show:

- Source
- Action (`provenance.action`)
- Surface (`provenance.surface`)
- Workflow (`provenance.workflow`)
- Model version
- Confidence
- Recorded timestamp

Unknown/missing values render as `Not available`.

## Fallback And Safety Rules

- Missing label record: show `❓` and `Not available` detail values.
- Missing/invalid provenance object or missing keys: no exception; show fallbacks.
- Missing or invalid confidence value: `Not available`.
- Missing timestamp: `Not available`.
- Overlay click for face not present in labeled list: no-op; do not throw.

## Architecture And Component Changes

### Backend

- `apps/api/app/repositories/photos_repo.py`
  - Extend face hydration for detail mode to join/lookup latest matching `face_labels` rows.
- `apps/api/app/schemas/photo_response.py`
  - Extend `PhotoDetailFace` schema with provenance fields.
- `apps/api/tests/test_photo_detail_api.py`
  - Add provenance-positive and provenance-missing assertions.

### Frontend

- `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
  - Pass provenance-enriched face records to assignment controls.
  - Render overlay badges and connect click behavior to expanded provenance row state.
- `apps/ui/src/pages/FaceAssignmentControls.tsx`
  - Add badge rendering and inline expandable details for labeled faces.
  - Add single-expanded-row state and overlay-trigger support.
- `apps/ui/src/styles/app-shell.css`
  - Add compact provenance badge styles and details-panel styles.
- `apps/ui/src/pages/FaceAssignmentControls.test.tsx`
  - Add tests for badge mapping, expand/collapse, overlay-to-row behavior, and fallback rendering.

## Testing Strategy

- API contract tests:
  - returns provenance fields when face label row exists
  - returns null provenance fields for legacy/missing rows
- UI tests:
  - badge symbol rendering by source type (`👤`, `🤖`, `💡`, `❓`)
  - inline panel toggle and single-expanded-row behavior
  - overlay badge opens correct row details
  - missing values shown as `Not available`
- Regression:
  - existing assignment/correction behavior remains unchanged

## Risks And Mitigations

- Risk: incorrect label row chosen when multiple historical rows exist.
  - Mitigation: deterministic latest-row ordering with explicit tie-break.
- Risk: emoji rendering differences across platforms.
  - Mitigation: keep visual symbol compact but provide explicit accessible labels and deterministic text in details panel.
- Risk: overcrowded overlays on small faces.
  - Mitigation: badge size tuned for compact footprint; details remain in list panel, not overlay body.

## Acceptance Criteria Mapping

- Label source/provenance visible in labeling UI contexts:
  - badges in correction rows and overlays.
- Users inspect provenance details without leaving workflow:
  - inline expandable panel in correction section.
- Missing provenance surfaced safely and explicitly:
  - `❓` badge + `Not available` detail fields.

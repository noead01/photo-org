# Library Advanced Faces Filter Design

Date: 2026-05-10

## Summary

Add a richer Faces filter to Library search that replaces dependence on simple `has_faces` semantics for face-centric workflows. The new filter supports:

- face-count range (`at least` / `at most`)
- top-certainty range over faces in each photo
- a checkbox for photos containing at least one face assigned to Unknown person

The filter must support slider-based interaction and preserve clean drag behavior consistent with Suggestions page controls.

## Goals

- Provide face-count range filtering using a dual-handle slider.
- Provide top-certainty range filtering using a dual-handle slider.
- Support unknown-person face filtering with explicit checkbox behavior.
- Ensure face-specific subfilters are inactive when zero-face-only filtering is selected.
- Keep query semantics deterministic and testable across UI, URL state, and backend query evaluation.

## Non-Goals

- Redesign non-face filter controls.
- Replace search pagination or sorting architecture.
- Introduce a separate search endpoint for face filters.
- Remove legacy `has_faces` backend support in this slice (compatibility can remain during migration).

## User-Facing Behavior

## Faces Filter Panel

The panel exposes:

1. Face count range slider (`0..10`, dual handle)
2. Top certainty range slider (`0..100`, dual handle)
3. `Has face assigned to unknown person` checkbox

### Face count slider semantics

- Left handle: minimum face count.
- Right handle: maximum face count.
- Right handle at `10` is displayed as `∞` and means unbounded max.
- Active face-count includes active non-dismissed faces only.

Examples:

- `0..0`: photos with zero faces only
- `2..5`: photos with 2 to 5 faces
- `1..∞`: photos with at least one face

### Top certainty slider semantics

- Dual handle on `0..100`.
- Applied with ANY-face semantics per photo:
  - a photo passes if at least one face in that photo has effective top certainty within range.

Effective top certainty per face:

- `100%` if face is human-confirmed assignment
- otherwise top machine suggestion confidence for that face

### Unknown person checkbox

- When checked, include photos where at least one active face is assigned to the system Unknown person identity.
- This is **at least one face**, not all faces.

### Zero-face-only disable rule

When count range is exactly `0..0`, face-attribute subfilters are inactive:

- top-certainty range is disabled/ignored
- unknown-person checkbox is disabled/ignored
- any other face-attribute-specific options in this panel are disabled/ignored

Helper text:

`Face-specific options are unavailable when only zero-face photos are selected.`

## Interaction Model

- Panel is accessed from the existing filter-chip entry pattern.
- Changes update live while editing.
- `Done` closes panel; no `Cancel` in this phase.
- Sliders must use drag behavior consistent with existing Suggestions confidence controls (smooth handle drag without noisy intermediate behavior regressions).

## Data Contract

Add a dedicated `faces` object under `SearchFilters`.

Proposed structure:

```json
{
  "filters": {
    "faces": {
      "min_count": 2,
      "max_count": null,
      "top_certainty_min": 0.65,
      "top_certainty_max": 1.0,
      "has_unknown_person": true
    }
  }
}
```

Fields:

- `min_count: int | null`
- `max_count: int | null` (`null` = unbounded)
- `top_certainty_min: float | null` (`0..1`)
- `top_certainty_max: float | null` (`0..1`)
- `has_unknown_person: bool | null`

`null` means the clause is omitted from query filtering, not zero.

## Serialization Rules (UI/URL/Request)

Defaults in UI can display `0..∞`, but serialization omits no-op defaults:

- if count range is default `0..∞`, omit both `min_count` and `max_count`
- if count range is `0..0`, omit `top_certainty_*` and `has_unknown_person`
- if certainty range is default `0..100` and active, it may still be omitted as no-op

URL-state parsing/serialization should round-trip deterministically.

## Backend Query Semantics

The new `faces` filter clauses compose with existing filters using `AND`.

### Face count

- apply `face_count >= min_count` when set
- apply `face_count <= max_count` when set
- count is over non-dismissed faces tied to the photo

### Top certainty range

- derive per-face effective certainty:
  - human-confirmed assigned face => `1.0`
  - otherwise top suggestion confidence for that face (if present)
- photo passes if any face certainty in photo is within `[top_certainty_min, top_certainty_max]`

### Unknown person

- pass when a photo has at least one active face assigned to the system Unknown person identity.
- resolve unknown identity robustly via canonical display name / known identity lookup, not hardcoded IDs.

## SRP-Oriented File Responsibilities

- `LibrarySearchForm.tsx`: panel UI and local interaction/session behavior only
- `libraryRouteSearchState.ts`: parse/serialize URL/query-state shape only
- `useLibraryResults.ts` (or request builder path): mapping UI state to request payload only
- `search_request.py`: request schema/validation only
- `photos_repo.py`: SQL/query filtering semantics only

Avoid duplicating certainty/count/unknown logic in multiple layers.

## Testing Strategy

### UI tests (`LibraryRoutePage.test.tsx`)

- face count slider changes emit expected filter payload
- `10` max is displayed as `∞` and treated as unbounded
- certainty range slider updates payload with decimal bounds
- unknown-person checkbox updates payload
- `0..0` disables/ignores face-attribute subfilters
- slider drag interactions remain stable

### URL state tests (`libraryRouteSearchState.test.ts`)

- parse/serialize roundtrip for face filter params
- omit no-op defaults (`0..∞`)
- enforce omission of face-attribute filters when `0..0`

### API/schema/repository tests

- schema validation for count/certainty bounds and min<=max
- repository filtering:
  - count range filtering
  - certainty ANY-face semantics
  - unknown-person inclusion behavior
  - conjunction with existing filters

## Risks and Mitigations

- Risk: uncertain unknown-person identity lookup in query layer.
  - Mitigation: centralize unknown-person resolution and test against assignment workflow behavior.
- Risk: slider UX regressions (jitter/noisy updates).
  - Mitigation: reuse existing Suggestions slider interaction pattern and add focused UI tests.
- Risk: duplicated logic across UI/query serialization/repository.
  - Mitigation: enforce SRP boundaries and keep each layer focused on one responsibility.


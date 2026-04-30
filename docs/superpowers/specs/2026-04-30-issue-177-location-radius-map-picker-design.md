# Issue #177 Location Radius Map Picker Design

Date: 2026-04-30
Issue: #177
Epic: #160

## Summary

Implement Search route location-radius filtering with a free, navigable map picker that lets users set center coordinates and radius via direct map interaction. The UX adds click-to-set-center plus drag-to-resize-circle behavior, keeps typed latitude/longitude/radius inputs synchronized, validates ranges before submit, and serializes deterministic `filters.location_radius` payloads only when valid.

## Goals

- deliver a map-driven location filter UX for `/search` without requiring provider credentials
- allow users to set location center and radius directly from map interaction
- keep location filter state explicit and removable through active chips
- block invalid location submissions with clear validation feedback
- preserve deterministic request semantics when location filters combine with date/person/text filters

## Non-Goals

- place-name search, geocoding, or reverse-geocoding
- automatic search execution while dragging map controls
- URL/deep-link synchronization for location state (tracked separately)
- backend contract changes for `location_radius`

## Existing Context

- backend already supports typed `filters.location_radius` with schema-level validation and radius defaults from issue #37
- search UI currently supports tokenized text chips (#174), date filters (#175), and person filters (#176) with one deterministic submit path
- current search behavior runs only on explicit submit or chip-removal actions; this issue keeps that execution model

## Chosen Approach

Use `leaflet` with OpenStreetMap tiles and a custom editable circle interaction in `SearchRoutePage`.

Why this approach:

- satisfies the required UX exactly: click map to set center, drag handle to set radius
- avoids API keys and paid providers
- avoids heavy plugin toolbars while keeping interaction logic local and testable

## Interaction Model

### Map creation and editing

- Show a `Location radius` section inside the existing search form.
- Render a Leaflet map initialized to neutral/global view.
- First click on map sets center and creates:
  - center marker
  - radius circle
  - draggable radius handle placed on circle edge
- initial radius defaults to `50` km when no prior radius value exists
- Dragging the radius handle updates `radius_km` continuously.
- Additional map click resets center to clicked location while preserving current radius when valid.

### Input synchronization

- Keep manual `latitude`, `longitude`, and `radius_km` inputs visible and editable.
- Map updates inputs immediately after click/drag interactions.
- Valid manual input updates map overlays immediately.
- Invalid manual input does not trigger request execution and surfaces validation messaging.

### Submit and clear behavior

- Map edits update filter state only; no automatic search execution.
- Search executes only when user presses `Search`, consistent with existing behavior.
- Active location filter appears as a removable chip:
  - `location: <lat>, <lon> (<radius_km> km)` with stable display rounding (`lat/lon` to 4 decimals, `radius_km` to 1 decimal)
- Removing the location chip:
  - clears location inputs
  - removes map circle/marker/handle
  - omits `filters.location_radius` from subsequent request payloads

## Validation Rules

Client-side validation gates submit for location state:

- latitude must be finite and between `-90` and `90`
- longitude must be finite and between `-180` and `180`
- radius must be finite and greater than `0`

When validation fails:

- submission is blocked
- a clear location validation message is shown near location controls
- existing results and other active filter state remain unchanged

Location filter is considered active only when all three location values are present and valid.

## Request Semantics

On submit, include location filter only when active:

```json
{
  "q": "<serialized query chips>",
  "filters": {
    "date": { "...": "..." },
    "person_names": ["..."],
    "location_radius": {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "radius_km": 12.5
    }
  },
  "sort": { "by": "shot_ts", "dir": "desc" },
  "page": { "limit": 24, "cursor": null }
}
```

- `filters.location_radius` composes with date/person filters under existing deterministic merge behavior.
- clearing location state removes only `location_radius`; other active filters stay intact.

## Technical Design

- Add dependencies:
  - `leaflet` in `apps/ui/package.json`
  - `@types/leaflet` in `apps/ui/package.json` dev dependencies
- Extend `apps/ui/src/pages/SearchRoutePage.tsx`:
  - add location draft and parsed state
  - add location validation helper(s)
  - extend `buildSearchFilters(...)` and request builder for `location_radius`
  - integrate a small map/editor subcomponent colocated in this file for issue scope
- Extend `apps/ui/src/styles/app-shell.css` with location panel/map/handle styling and responsive behavior.

## Accessibility And Failure Handling

- keep manual numeric inputs as first-class controls so location filtering still works if tiles fail
- map interactions remain additive, not exclusive; typed input is always available
- if tile layer fails, show non-blocking helper text and keep manual location filtering available

## Testing Strategy

Update `apps/ui/src/pages/SearchRoutePage.test.tsx` with focused tests:

- submits valid location filter as `filters.location_radius`
- blocks submit when latitude/longitude/radius are invalid and shows validation message
- removes location chip and submits without `location_radius` afterwards
- combines location filter with existing date/person filters deterministically
- preserves no-auto-search behavior when location fields change before submit

For unit tests, mock map-layer/event surfaces enough to verify state and payload semantics.
Do not require pixel-level drag simulation in this issue’s unit scope.

## Risks And Mitigations

- Risk: map interaction complexity introduces flaky tests.
  - Mitigation: test deterministic state/payload effects; keep pointer-precision behavior outside unit scope.
- Risk: map provider availability or tile load issues.
  - Mitigation: treat map as enhancement and preserve manual input path.
- Risk: UX confusion from mixed input and map editing.
  - Mitigation: keep synchronized values visible and surface one clear active location chip.

## Acceptance Criteria Mapping (Issue #177)

- location-radius inputs validate and prevent invalid submissions:
  - covered by explicit range validation and submit gating.
- active location filter state is visible and removable:
  - covered by location chip plus clear behavior resetting map/input state.
- valid inputs generate deterministic request payload semantics:
  - covered by typed `filters.location_radius` inclusion only for valid active location state.

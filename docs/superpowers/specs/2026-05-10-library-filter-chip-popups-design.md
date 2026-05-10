# Library Filter Chip Popups Design

Date: 2026-05-10

## Summary

Improve Library filter-selection UX by replacing the single "Filter labels" disclosure editor with per-filter chip entry points. Each filter type opens independently, only one filter editor can be open at a time, and active filter chips under the form remain unchanged for quick removal.

## Goals

- Use filter-type chips as the entry point for editing each filter.
- Avoid showing all filter controls at once.
- Keep live updates for multi-instance filters.
- Support explicit close/confirm semantics per filter type.
- Keep active-filter removal chips unchanged.
- Keep behavior mobile-friendly with inline, non-floating editors.

## Non-Goals

- No backend API or search payload schema changes.
- No change to the existing active-filter chip row semantics.
- No new filter families beyond current Date/Person/Location/Album/Path hints/Has faces.

## Interaction Model

The filter entry row becomes six chips:

1. Date
2. Person
3. Location
4. Album
5. Path hints
6. Has faces

Chip behavior:

- Clicking a closed chip opens its editor panel inline below the chip row.
- Clicking the currently open chip closes its panel.
- Opening one panel closes any other currently open panel.
- Chip active state reflects whether that filter currently has applied values.

## Per-Filter Behavior

### Date

- Opens Date panel.
- Action buttons: `Cancel` only.
- `Cancel` reverts `fromDate` and `toDate` to the snapshot captured when Date panel opened, then closes.

### Person

- Opens Person panel.
- Action buttons: `Done` only.
- Live updates remain enabled while adding/removing multiple people.
- Panel closes only when `Done` is clicked (or another chip is opened).

### Location

- Opens Location panel.
- Action buttons: `Apply` and `Cancel`.
- `Apply` validates current location fields; if valid, close panel; if invalid, keep panel open and show validation.
- `Cancel` reverts location fields to the snapshot captured when Location panel opened, then closes.

### Album

- Opens Album panel.
- Action buttons: `Done` only.
- Live multi-select updates remain enabled.

### Path hints

- Opens Path-hints panel.
- Action buttons: `Done` only.
- Live multi-select updates remain enabled.

### Has faces

- No popup panel.
- Chip click cycles live through:
  - `Any` (no filter)
  - `With faces`
  - `Without faces`
  - back to `Any`

## State Model

Existing filter state remains owned by `LibraryRoutePage`. `LibrarySearchForm` gets lightweight panel-session state:

- `openPanel: "date" | "person" | "location" | "album" | "pathHints" | null`
- `dateSnapshot` captured on Date panel open
- `locationSnapshot` captured on Location panel open

Lifecycle:

1. Opening Date or Location captures a snapshot for cancel-revert.
2. `Cancel` restores snapshot for Date/Location and closes.
3. `Done` for Person/Album/Path hints closes without rollback.
4. `Apply` for Location closes only on valid input.
5. Has-faces chip updates directly without panel state.

## Component-Level Changes

### `apps/ui/src/pages/library/LibrarySearchForm.tsx`

- Replace current single disclosure toggle ("Filter labels" + Edit/Hide) with chip entry row.
- Render panel content by `openPanel`, one at a time.
- Add per-panel action controls:
  - Date: `Cancel`
  - Person: `Done`
  - Location: `Apply`, `Cancel`
  - Album: `Done`
  - Path hints: `Done`
- Move has-faces interaction from panel buttons to direct chip cycling behavior.
- Preserve existing handlers and live-update flow for person, album, and path hints.

### `apps/ui/src/pages/search/FacetFilterPanel.tsx`

- Refactor responsibilities so `Has faces` controls are removed from this panel path.
- Reuse or split album/path-hints controls as needed by `LibrarySearchForm` without changing data semantics.

### `apps/ui/src/styles/app-shell.css`

- Add styles for filter entry chips that act as selectors/openers.
- Add inline editor panel styling suitable for desktop and mobile.
- Add panel action-row styling for `Done`, `Apply`, `Cancel`.
- Keep active-filter chip row styles unchanged.

## Accessibility

- Entry chips remain keyboard operable (`button` semantics).
- Only one panel visible at a time to reduce focus ambiguity.
- Panel actions have explicit labels (`Done`, `Apply`, `Cancel`).
- Existing validation messaging remains attached to relevant fields.

## Testing Plan

Update `apps/ui/src/pages/LibraryRoutePage.test.tsx` with:

1. Opening one filter panel closes the previously open panel.
2. Person panel stays open across multiple additions until `Done`.
3. Date `Cancel` restores the snapshot state.
4. Location `Cancel` restores the snapshot state.
5. Location `Apply` closes on valid location and stays open on invalid location.
6. Has-faces chip cycles `Any -> With -> Without -> Any`.
7. Active-filter removal chips still remove filters correctly (regression guard).

## Risks and Mitigations

- Risk: confusion between entry chips and active-filter chips.
  - Mitigation: preserve visual distinction and labels; keep active-filter row untouched.
- Risk: state edge cases when switching panels mid-edit.
  - Mitigation: snapshot only Date/Location, close previous panel deterministically.
- Risk: regression in facet controls due to has-faces extraction.
  - Mitigation: add explicit tests around has-faces cycle and path-hints panel behavior.


# Suggestions Exclude Filter Design

Date: 2026-05-06
Scope: Suggestions page exclude-people filter and persisted client-side filter state

## Summary

Add an exclude-people filter to the Suggestions page so reviewers can suppress faces whose current top suggestion matches selected people. Persist both the exclude-people selection and the existing `Minimum certainty` slider in `localStorage` so these preferences survive route changes, reloads, and leaving and returning to the site.

## Goals

- let users exclude one or more people from the suggestions review flow
- hide faces when their highest-confidence suggestion belongs to an excluded person
- hide photo cards that have no remaining visible faces after exclusion
- persist the exclude-people filter in `localStorage`
- persist the `Minimum certainty` slider value in `localStorage`
- keep confirmation behavior aligned with the visible filtered set only

## Non-Goals

- changing the suggestions API contract
- adding server-side support for exclude filters
- changing suggestion ranking or confidence calculation
- persisting per-face checkbox selections across reloads

## Decision Snapshot

- people source: existing `/api/v1/people` directory
- exclude state identity: `person_id`
- exclude state presentation: badge-style toggle controls plus active removable chips
- filter execution: client-side after suggestions payload load
- confidence persistence: `localStorage`
- malformed stored data handling: ignore and fall back to defaults

## UX Behavior

The Suggestions header keeps the `Minimum certainty` slider and adds an `Exclude people` control populated from the people directory. Each person renders as a toggleable badge. Selecting a badge excludes that person; selecting it again removes the exclusion.

Active exclusions also render as removable chips so the current filter state remains obvious even when the people directory is long. The page continues to default visible faces to checked for confirmation.

## Filtering Rules

- fetch suggestions from the existing endpoint using the current minimum-confidence threshold
- after payload load, remove any face whose `top_suggestion.person_id` is in the excluded set
- if a photo has zero faces left after exclusion, omit that photo from the rendered grid
- `Pending photos` should reflect the visible filtered payload, not the raw API total, so the page summary matches what the user can act on
- confirmation requests must include only currently visible and currently checked face ids

## Persistence Model

Store both values in `window.localStorage` under Suggestions-specific keys:

- excluded people: array of `person_id` strings
- minimum certainty: integer percent from `0` to `100`

On initial render:

- load both values from `localStorage`
- validate shape and bounds
- fall back to an empty excluded set and `0` percent if data is missing or invalid

On user changes:

- update React state immediately
- write the normalized value back to `localStorage`

## Implementation Notes

- keep a small Suggestions-specific storage helper near the route page, similar in style to the existing library route memory helper
- fetch the people directory once on page load and tolerate failure by rendering no people badges rather than blocking the suggestions workflow
- maintain filtering in derived UI state rather than mutating raw API payloads in place
- preserve the existing page reset behavior when the minimum-confidence slider changes
- also reset to page `1` when the exclude-people filter changes so pagination stays predictable

## Testing Strategy

Add or extend route tests to cover:

- restoring the persisted minimum-confidence slider value from `localStorage`
- restoring persisted excluded people from `localStorage`
- excluding a person hides matching faces from the rendered list
- excluding a person hides photo cards with no remaining visible faces
- toggling an exclusion updates persisted state
- confirmation submits only visible checked face ids after filtering
- invalid stored values fall back safely to defaults

## Verification Commands

Run from `apps/ui`:

1. `npm run test -- SuggestionsRoutePage`

## Risks And Mitigations

- risk: visible item counts diverge from API totals
  - mitigation: compute displayed counts from filtered payload and keep the copy scoped to what the user can act on
- risk: stale excluded `person_id`s remain in storage after people directory changes
  - mitigation: keep stored ids harmless; they simply stop matching if no suggestion references them
- risk: localStorage access throws in restricted environments
  - mitigation: guard storage access and fall back to in-memory defaults

## Open Questions

- none for this slice

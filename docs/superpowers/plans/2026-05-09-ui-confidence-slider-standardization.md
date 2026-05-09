# UI Confidence Slider Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad hoc confidence controls with a reusable, accessible slider abstraction for single-threshold and min/max confidence selection.

**Architecture:** Add one app-owned confidence slider wrapper backed by a battle-tested headless slider. Prefer `@radix-ui/react-slider` because it is lightweight, controlled, supports multiple thumbs, and does not impose a full component design system.

**Tech Stack:** React 18, TypeScript, `@radix-ui/react-slider`, Testing Library, Vitest.

---

## Files

- Modify: `apps/ui/package.json`
- Create: `apps/ui/src/pages/shared/ConfidenceSlider.tsx`
- Create: `apps/ui/src/pages/shared/ConfidenceSlider.test.tsx`
- Modify: `apps/ui/src/pages/suggestions/SuggestionsFilters.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

## Current Problem

- Suggestions uses two independent native range inputs for min/max certainty in `apps/ui/src/pages/suggestions/SuggestionsFilters.tsx:36`.
- Library uses a decimal text input for suggestion threshold in `apps/ui/src/pages/library/LibrarySearchForm.tsx:200`.
- Min/max consistency lives in the Suggestions parent at `apps/ui/src/pages/SuggestionsRoutePage.tsx:184`.

## Tasks

### Task 1: Add Slider Dependency

- [ ] Install dependency: `npm --prefix apps/ui install @radix-ui/react-slider`.
- [ ] Confirm `apps/ui/package.json` and lockfile are updated.
- [ ] Run: `npm --prefix apps/ui run build`.
- [ ] Expected: build succeeds with the new dependency available.

### Task 2: Create Confidence Slider Wrapper

- [ ] Create `ConfidenceSlider.tsx` with two exported components:
`ConfidenceSingleSlider` and `ConfidenceRangeSlider`.
- [ ] Use integer percent values in component props: `0` through `100`.
- [ ] Render visible labels that include the current percentage.
- [ ] Set accessible labels for thumbs:
`Suggestion threshold`, `Minimum suggestion certainty`, and `Maximum suggestion certainty`.
- [ ] For range mode, enforce `min <= max` through the slider value rather than parent correction code.
- [ ] Keep styling hooks app-owned with class names such as `confidence-slider`, `confidence-slider-track`, `confidence-slider-range`, and `confidence-slider-thumb`.

### Task 3: Test Slider Wrapper

- [ ] Add `ConfidenceSlider.test.tsx`.
- [ ] Cover single value rendering and callback.
- [ ] Cover range value rendering and callback.
- [ ] Cover disabled state.
- [ ] Run: `npm --prefix apps/ui test -- ConfidenceSlider.test.tsx`.
- [ ] Expected: wrapper tests pass.

### Task 4: Replace Suggestions Min/Max Inputs

- [ ] Modify `SuggestionsFilters` to accept a single `onConfidenceRangeChange(minPercent, maxPercent)` callback instead of separate min/max callbacks.
- [ ] Render `ConfidenceRangeSlider`.
- [ ] Update `SuggestionsRoutePage` to update both state values from the range callback and reset page to `1`.
- [ ] Remove parent-side correction code that manually clamps min/max against each other.
- [ ] Run: `npm --prefix apps/ui test -- SuggestionsRoutePage.test.tsx`.
- [ ] Expected: existing min/max query tests still pass.

### Task 5: Replace Library Suggestion Threshold Text Input

- [ ] Modify `LibrarySearchForm` so `personCertaintyMode === "include_suggestions"` renders `ConfidenceSingleSlider`.
- [ ] Keep parent state as `suggestionConfidenceMinDraft` string until query-state refactor lands.
- [ ] Convert percent to decimal string before calling `onSuggestionConfidenceMinDraftChange`.
- [ ] Preserve request behavior validated by `LibraryRoutePage.test.tsx` expecting `suggestion_confidence_min: 0.91`.
- [ ] Run: `npm --prefix apps/ui test -- LibraryRoutePage.test.tsx`.
- [ ] Expected: person certainty and suggestion threshold tests pass.

### Task 6: Final Verification

- [ ] Run: `npm --prefix apps/ui test`.
- [ ] Run: `npm --prefix apps/ui run build`.
- [ ] Confirm `rg -n "type=\\\"range\\\"" apps/ui/src` only reports intentional non-confidence controls, such as photo image scale.

## Acceptance Criteria

- Suggestions uses a combined min/max slider.
- Library suggestion threshold uses the same confidence slider visual/behavioral primitive.
- Confidence values remain serialized to backend/API calls as decimal values where required.
- Photo detail image scale may continue using native range because it is not a confidence selector.


# Suggestions Exclude Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persisted Suggestions page filters for minimum certainty and excluded people, and suppress visible suggestions whose top match is excluded.

**Architecture:** Keep the API contract unchanged and implement filtering entirely in the UI route. Add a small Suggestions-specific `localStorage` helper, load the people directory once for badge toggles, derive the visible payload from the fetched suggestions payload plus local filter state, and keep confirmation scoped to the visible checked face ids.

**Tech Stack:** React, TypeScript, React Testing Library, Vitest, existing app-shell CSS

---

### Task 1: Persisted Suggestions Filter State

**Files:**
- Create: `apps/ui/src/pages/suggestions/suggestionsRouteMemory.ts`
- Test: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add tests in `apps/ui/src/pages/SuggestionsRoutePage.test.tsx` that preload `window.localStorage` and assert:

```ts
window.localStorage.setItem(
  "photo-org:suggestions:filters",
  JSON.stringify({ minConfidencePercent: 90, excludedPersonIds: ["person-2"] })
);
```

The rendered page should:

```ts
expect(await screen.findByDisplayValue("90")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "Exclude Blair" })).toHaveAttribute(
  "aria-pressed",
  "true"
);
```

Also add an invalid-storage test:

```ts
window.localStorage.setItem("photo-org:suggestions:filters", "{bad json");
expect(await screen.findByDisplayValue("0")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "Exclude Alex" })).toHaveAttribute(
  "aria-pressed",
  "false"
);
```

- [ ] **Step 2: Run the targeted tests to verify failure**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: FAIL because the page does not read persisted filter state or render exclude controls.

- [ ] **Step 3: Write the storage helper**

Create `apps/ui/src/pages/suggestions/suggestionsRouteMemory.ts` with a guarded `localStorage` helper:

```ts
const SUGGESTIONS_FILTERS_KEY = "photo-org:suggestions:filters";

export interface StoredSuggestionsFilterState {
  minConfidencePercent: number;
  excludedPersonIds: string[];
}

function resolveLocalStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
```

Include:

```ts
export function loadSuggestionsFilterState(): StoredSuggestionsFilterState | null
export function saveSuggestionsFilterState(state: StoredSuggestionsFilterState): void
```

Validation rules:
- `minConfidencePercent` must be an integer between `0` and `100`
- `excludedPersonIds` must be an array of non-empty strings
- invalid payloads return `null`

- [ ] **Step 4: Run the targeted tests to verify progress**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: still FAIL because the route page is not using the new helper yet.

### Task 2: Exclude People UI And Derived Visible Payload

**Files:**
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- Test: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`

- [ ] **Step 1: Write the failing tests**

Extend `apps/ui/src/pages/SuggestionsRoutePage.test.tsx` with:

```ts
expect(await screen.findByRole("button", { name: "Exclude Alex" })).toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "Exclude Blair" }));
expect(screen.queryByText("Face 2: Blair (82.0%)")).not.toBeInTheDocument();
expect(window.localStorage.getItem("photo-org:suggestions:filters")).toContain("person-2");
```

Add a whole-photo suppression case:

```ts
expect(screen.queryByText("/photos/photo-2.jpg")).not.toBeInTheDocument();
expect(screen.getByText("Pending photos: 1")).toBeInTheDocument();
```

Add slider persistence coverage:

```ts
fireEvent.change(screen.getByLabelText("Minimum suggestion certainty"), {
  target: { value: "90" }
});
expect(window.localStorage.getItem("photo-org:suggestions:filters")).toContain(
  "\"minConfidencePercent\":90"
);
```

- [ ] **Step 2: Run the targeted tests to verify failure**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: FAIL because the route has no people-directory fetch, no exclude badges, and no derived visible filtering.

- [ ] **Step 3: Write the minimal route implementation**

In `apps/ui/src/pages/SuggestionsRoutePage.tsx`:

- add a `PersonRecord` type with `person_id` and `display_name`
- add `fetchPeopleDirectory()` calling `/api/v1/people`
- initialize `minConfidencePercent` and `excludedPersonIds` from `loadSuggestionsFilterState()`
- keep the fetched suggestions payload as raw state, then derive visible photos with:

```ts
const visibleItems = useMemo(() => {
  if (!payload) {
    return [] as SuggestionPhoto[];
  }
  return payload.items
    .map((photo) => ({
      ...photo,
      faces: photo.faces.filter(
        (face) => !excludedPersonIds.has(face.top_suggestion.person_id)
      )
    }))
    .filter((photo) => photo.faces.length > 0);
}, [payload, excludedPersonIds]);
```

- derive `currentPageFaceIdsOrdered` from `visibleItems`
- save filter state whenever `minConfidencePercent` or `excludedPersonIds` changes
- fetch the people directory once in `useEffect`
- toggle exclusions by `person_id`, reset page to `1` when exclusions change
- render toggle badges:

```tsx
<button
  type="button"
  className={excluded ? "search-chip search-chip-active" : "search-chip"}
  aria-pressed={excluded}
  aria-label={`Exclude ${person.display_name}`}
>
  {person.display_name}
</button>
```

- render active removable chips using excluded people whose directory entries are known
- show `Pending photos` from `visibleItems.length`

- [ ] **Step 4: Add minimal supporting styles**

In `apps/ui/src/styles/app-shell.css`, add compact layout styles for:
- `.suggestions-header-actions`
- `.suggestions-filter-group`
- `.suggestions-people-filter`
- `.suggestions-active-filters`

Reuse the existing `.search-chip` styling rather than inventing a new badge component.

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: PASS for the Suggestions route test file.

### Task 3: Confirmation Scope And Final Verification

**Files:**
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/SuggestionsRoutePage.tsx` (only if needed)

- [ ] **Step 1: Write the failing confirmation-scope test**

Add a test that excludes one person, confirms the remaining faces, and asserts:

```ts
await waitFor(() => {
  expect(fetchMock).toHaveBeenCalledWith("/api/v1/suggestions/confirmations", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Face-Validation-Role": "contributor"
    },
    body: JSON.stringify({ face_ids: ["face-1"] })
  });
});
```

Where the raw payload also included a hidden excluded face such as `face-2`.

- [ ] **Step 2: Run the targeted tests to verify failure if behavior is still wrong**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: either PASS immediately because visible-face scoping is already correct, or FAIL with excluded hidden face ids still being submitted.

- [ ] **Step 3: Adjust the confirmation path only if the test fails**

Ensure confirmation uses the derived visible face ordering:

```ts
const checkedFaceIdsOnCurrentPage = currentPageFaceIdsOrdered.filter((faceId) =>
  selectedFaceIds.has(faceId)
);
```

No raw payload face ids should be used for confirmation after filtering.

- [ ] **Step 4: Run final verification**

Run:

```bash
npm --prefix apps/ui test -- SuggestionsRoutePage
```

Expected: PASS with `0` failures for the targeted Suggestions route tests.

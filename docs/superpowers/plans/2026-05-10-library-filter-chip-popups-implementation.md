# Library Filter Chip Popups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Library route's all-at-once filter editor with per-filter chip popups that open one at a time, keep live updates where required, and add Done/Apply/Cancel behavior by filter type.

**Architecture:** Keep filter source-of-truth in `LibraryRoutePage` and implement popup/session behavior in `LibrarySearchForm`. Keep active filter removal chips unchanged. Move has-faces interaction to a direct cycling chip and keep album/path-hint controls in their own popup sections.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing app-shell CSS.

---

## SRP Guardrails (Apply To Every Task)

- Keep container orchestration in `LibrarySearchForm.tsx` and avoid leaking panel-session logic into unrelated files.
- Keep reusable facet-option rendering concerns in `FacetFilterPanel.tsx`; do not re-embed duplicate album/path-hint control logic in multiple places.
- Keep presentation-only styling in `app-shell.css`; no behavior encoded in CSS class naming or selector hacks.
- Keep tests in `LibraryRoutePage.test.tsx` focused on user-observable behavior, not implementation internals.
- Before each task commit, confirm each touched file still has one clear responsibility and remove any helper/function that crosses responsibilities.

---

### Task 1: Add One-Panel Filter Chip Controller In `LibrarySearchForm`

**Files:**
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Write failing tests for panel switching and per-chip entry points**

```tsx
it("opens one filter panel at a time from filter chips", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  await user.click(screen.getByRole("button", { name: "Person filter type" }));
  expect(screen.getByLabelText("Person filter")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Album filter type" }));
  expect(screen.queryByLabelText("Person filter")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Done album filters" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run targeted test command and verify failure**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx -t "opens one filter panel at a time from filter chips"`

Expected: FAIL with missing `Person filter type`/`Album filter type` controls.

- [ ] **Step 3: Replace disclosure state with `openPanel` state and chip row**

```tsx
type OpenPanel = "date" | "person" | "location" | "album" | "pathHints" | null;

const [openPanel, setOpenPanel] = useState<OpenPanel>(null);

function handleTogglePanel(panel: Exclude<OpenPanel, null>) {
  setOpenPanel((current) => (current === panel ? null : panel));
}

<div className="search-filter-entry-row" aria-label="Filter labels">
  <button type="button" aria-label="Date filter type" onClick={() => handleTogglePanel("date")}>Date</button>
  <button type="button" aria-label="Person filter type" onClick={() => handleTogglePanel("person")}>Person</button>
  <button type="button" aria-label="Location filter type" onClick={() => handleTogglePanel("location")}>Location</button>
  <button type="button" aria-label="Album filter type" onClick={() => handleTogglePanel("album")}>Album</button>
  <button type="button" aria-label="Path hints filter type" onClick={() => handleTogglePanel("pathHints")}>Path hints</button>
  <button type="button" aria-label="Has faces filter type">Has faces</button>
</div>

{openPanel === "person" ? (
  <div className="search-filter-panel" aria-label="Person filters panel">
    <div className="search-person-row">
      <label htmlFor="search-person-input">Person filter</label>
      <div className="search-person-input-row">
        <input id="search-person-input" type="text" value={personDraft} onChange={(event) => onPersonDraftChange(event.target.value)} />
        <button type="button" onClick={onAddPersonFilter}>Add person filter</button>
      </div>
    </div>
  </div>
) : null}
{openPanel === "album" ? (
  <div className="search-filter-panel" aria-label="Album filters panel">
    <FacetFilterPanel
      selectedAlbumIds={selectedAlbumIds}
      pathHintFilters={pathHintFilters}
      albumOptions={albumFilterOptions}
      pathHintCounts={facetPathHintCounts}
      onToggleAlbum={onToggleAlbumFilter}
      onClearAllAlbums={onClearAllAlbumFilters}
      onTogglePathHint={onTogglePathHintFilter}
      onClearAllPathHints={onClearAllPathHints}
    />
  </div>
) : null}
```

- [ ] **Step 4: Keep existing filter sections, but render each under its own conditional panel**

```tsx
{openPanel === "date" ? (
  <div className="search-filter-panel" aria-label="Date filters panel">
    <div className="search-date-row">
      <label htmlFor="search-date-from">From date</label>
      <input id="search-date-from" type="date" value={fromDate} onChange={(event) => onFromDateChange(event.target.value)} />
      <label htmlFor="search-date-to">To date</label>
      <input id="search-date-to" type="date" value={toDate} onChange={(event) => onToDateChange(event.target.value)} />
    </div>
  </div>
) : null}

{openPanel === "person" ? (
  <div className="search-filter-panel" aria-label="Person filters panel">
    <div className="search-person-row">
      <label htmlFor="search-person-input">Person filter</label>
      <div className="search-person-input-row">
        <input id="search-person-input" type="text" value={personDraft} onChange={(event) => onPersonDraftChange(event.target.value)} />
        <button type="button" onClick={onAddPersonFilter}>Add person filter</button>
      </div>
    </div>
  </div>
) : null}
```

- [ ] **Step 5: Re-run focused panel-switching test**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx -t "opens one filter panel at a time from filter chips"`

Expected: PASS.

- [ ] **Step 6: SRP checkpoint for Task 1**

Confirm:
- `LibrarySearchForm.tsx` only coordinates chip/panel state and delegates filter mutations through existing callbacks.
- No new duplicated filter rendering logic appears across panel sections.
- Tests assert interaction behavior only.

- [ ] **Step 7: Commit Task 1**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/LibrarySearchForm.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "feat: add per-filter chip entry panels in library search form"
```

### Task 2: Implement Button Semantics (Done/Apply/Cancel) and Revert Snapshots

**Files:**
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Write failing tests for Date cancel revert**

```tsx
it("reverts date edits on cancel", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library?from=2024-01-01&to=2024-01-31");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  await user.click(screen.getByRole("button", { name: "Date filter type" }));
  await user.clear(screen.getByLabelText("From date"));
  await user.type(screen.getByLabelText("From date"), "2024-02-01");
  await user.click(screen.getByRole("button", { name: "Cancel date filters" }));

  await user.click(screen.getByRole("button", { name: "Date filter type" }));
  expect(screen.getByLabelText("From date")).toHaveValue("2024-01-01");
});
```

- [ ] **Step 2: Write failing tests for Location apply/cancel behavior**

```tsx
it("applies valid location and closes panel on apply", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  await user.click(screen.getByRole("button", { name: "Location filter type" }));
  await user.type(screen.getByLabelText("Latitude"), "40.7");
  await user.type(screen.getByLabelText("Longitude"), "-74.0");
  await user.type(screen.getByLabelText("Radius (km)"), "3");
  await user.click(screen.getByRole("button", { name: "Apply location filters" }));

  expect(screen.queryByLabelText("Location filters panel")).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Write failing test for automatic Date panel close after both dates are set**

```tsx
it("auto-closes date panel when both dates are chosen", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  await user.click(screen.getByRole("button", { name: "Date filter type" }));
  await user.type(screen.getByLabelText("From date"), "2024-01-01");
  await user.type(screen.getByLabelText("To date"), "2024-01-31");

  expect(screen.queryByLabelText("Date filters panel")).not.toBeInTheDocument();
});
```

- [ ] **Step 4: Add snapshot state and open-time capture for date/location**

```tsx
const [dateSnapshot, setDateSnapshot] = useState<{ fromDate: string; toDate: string } | null>(null);
const [locationSnapshot, setLocationSnapshot] = useState<{
  latitudeDraft: string;
  longitudeDraft: string;
  radiusDraft: string;
} | null>(null);

function openPanel(panel: Exclude<OpenPanel, null>) {
  if (panel === "date") {
    setDateSnapshot({ fromDate, toDate });
  }
  if (panel === "location") {
    setLocationSnapshot({ latitudeDraft, longitudeDraft, radiusDraft });
  }
  setOpenPanel(panel);
}
```

- [ ] **Step 5: Add Date auto-close effect for complete valid range**

```tsx
useEffect(() => {
  if (openPanel !== "date") {
    return;
  }
  if (!fromDate || !toDate) {
    return;
  }
  if (dateRangeError) {
    return;
  }
  setOpenPanel(null);
}, [openPanel, fromDate, toDate, dateRangeError]);
```

- [ ] **Step 6: Add Date cancel and Location apply/cancel action rows**

```tsx
{openPanel === "date" ? (
  <div className="search-filter-panel-actions">
    <button
      type="button"
      onClick={() => {
        if (dateSnapshot) {
          onFromDateChange(dateSnapshot.fromDate);
          onToDateChange(dateSnapshot.toDate);
        }
        setOpenPanel(null);
      }}
    >
      Cancel date filters
    </button>
  </div>
) : null}

{openPanel === "location" ? (
  <div className="search-filter-panel-actions">
    <button
      type="button"
      onClick={() => {
        if (!locationError) {
          setOpenPanel(null);
        }
      }}
    >
      Apply location filters
    </button>
    <button
      type="button"
      onClick={() => {
        if (locationSnapshot) {
          onLatitudeDraftChange(locationSnapshot.latitudeDraft);
          onLongitudeDraftChange(locationSnapshot.longitudeDraft);
          onRadiusDraftChange(locationSnapshot.radiusDraft);
        }
        setOpenPanel(null);
      }}
    >
      Cancel location filters
    </button>
  </div>
) : null}
```

- [ ] **Step 7: Add Done buttons for Person/Album/Path hints panels**

```tsx
<button type="button" onClick={() => setOpenPanel(null)}>
  Done person filters
</button>

<button type="button" onClick={() => setOpenPanel(null)}>
  Done album filters
</button>

<button type="button" onClick={() => setOpenPanel(null)}>
  Done path hint filters
</button>
```

- [ ] **Step 8: Run targeted tests for cancel/apply/auto-close/done flows**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx -t "reverts date edits on cancel|applies valid location and closes panel on apply|auto-closes date panel when both dates are chosen|person panel stays open"`

Expected: PASS.

- [ ] **Step 9: SRP checkpoint for Task 2**

Confirm:
- Snapshot/revert logic stays in `LibrarySearchForm.tsx` and is scoped to Date/Location only.
- `LibraryRoutePage.tsx` ownership of filter source-of-truth is unchanged.
- Tests remain behavior-level.

- [ ] **Step 10: Commit Task 2**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/LibrarySearchForm.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "feat: add filter panel done apply cancel semantics"
```

### Task 3: Extract Has-Faces Cycle Chip and Split Facet UI Responsibilities

**Files:**
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Modify: `apps/ui/src/pages/search/FacetFilterPanel.tsx`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Write failing test for has-faces chip cycle**

```tsx
it("cycles has-faces chip any with without any", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  const chip = screen.getByRole("button", { name: "Has faces filter type" });
  await user.click(chip); // any -> with
  expect(screen.getByText("has faces: yes")).toBeInTheDocument();
  await user.click(chip); // with -> without
  expect(screen.getByText("has faces: no")).toBeInTheDocument();
  await user.click(chip); // without -> any
  expect(screen.queryByText(/has faces:/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Implement cycle helper and connect to has-faces chip click**

```tsx
function resolveNextHasFacesFilter(current: boolean | null): boolean | null {
  if (current === null) return true;
  if (current === true) return false;
  return null;
}

<button
  type="button"
  aria-label="Has faces filter type"
  className={hasFacesFilter !== null ? "search-filter-chip search-filter-chip-active" : "search-filter-chip"}
  onClick={() => {
    const nextValue = resolveNextHasFacesFilter(hasFacesFilter);
    if (nextValue === null) {
      onClearHasFacesFilter();
      return;
    }
    onToggleHasFacesFilter(nextValue);
  }}
>
  Has faces
</button>
```

- [ ] **Step 3: Remove has-faces controls from facet panel and use only album/path hints popup sections**

```tsx
// FacetFilterPanel props no longer include hasFaces* fields.
type FacetFilterPanelProps = {
  selectedAlbumIds: string[];
  pathHintFilters: string[];
  albumOptions: Array<{ albumId: string; albumName: string }>;
  pathHintCounts: FacetCountEntry[];
  onToggleAlbum: (albumId: string) => void;
  onClearAllAlbums: () => void;
  onTogglePathHint: (pathHint: string) => void;
  onClearAllPathHints: () => void;
};
```

- [ ] **Step 4: Run has-faces and facet regression tests**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx -t "cycles has-faces chip|shows album filter controls and chips with album names"`

Expected: PASS.

- [ ] **Step 5: SRP checkpoint for Task 3**

Confirm:
- `Has faces` interaction exists in one place only (chip entry control path).
- `FacetFilterPanel.tsx` responsibility is reduced to album/path-hint option sections.
- No cross-file responsibility duplication.

- [ ] **Step 6: Commit Task 3**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/LibrarySearchForm.tsx apps/ui/src/pages/search/FacetFilterPanel.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "feat: add has-faces chip cycle and split facet panels"
```

### Task 4: Style The New Chip Entry Row And Inline Panels For Mobile/Desktop

**Files:**
- Modify: `apps/ui/src/styles/app-shell.css`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Add failing assertion that new panel action controls are visible**

```tsx
it("shows panel action controls per filter type", async () => {
  const user = userEvent.setup();
  renderLibraryAt("/library");
  await screen.findByRole("heading", { name: "Library", level: 1 });

  await user.click(screen.getByRole("button", { name: "Path hints filter type" }));
  expect(screen.getByRole("button", { name: "Done path hint filters" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Add CSS for new entry row and panel actions without touching active chip row**

```css
.search-filter-entry-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.45rem 0.55rem;
}

.search-filter-entry-chip {
  border: 1px solid #cbd5e1;
  background: #ffffff;
  color: #334155;
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
  font: inherit;
}

.search-filter-panel {
  display: grid;
  gap: 0.55rem;
  padding: 0 0.55rem 0.55rem;
}

.search-filter-panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  justify-content: flex-end;
}

@media (max-width: 700px) {
  .search-filter-panel-actions {
    justify-content: stretch;
  }

  .search-filter-panel-actions button {
    flex: 1 1 auto;
  }
}
```

- [ ] **Step 3: Apply new class names in `LibrarySearchForm.tsx`**

```tsx
<button
  type="button"
  className={isActive ? "search-filter-entry-chip search-filter-chip-active" : "search-filter-entry-chip"}
  aria-label="Person filter type"
  onClick={() => handleTogglePanel("person")}
>
  Person
</button>
```

- [ ] **Step 4: Run full library route test file**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx`

Expected: PASS.

- [ ] **Step 5: SRP checkpoint for Task 4**

Confirm:
- `app-shell.css` additions are limited to layout/styling for entry chips and panel action rows.
- No behavior assumptions or feature branching encoded in style selectors.

- [ ] **Step 6: Commit Task 4**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/styles/app-shell.css apps/ui/src/pages/library/LibrarySearchForm.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "style: add inline per-filter panel layout for library filters"
```

### Task 5: Final Verification Before PR

**Files:**
- Verify only; no file edits expected.

- [ ] **Step 1: Run focused UI tests for touched filter-related files**

Run: `npm --prefix apps/ui test -- --runInBand src/pages/LibraryRoutePage.test.tsx src/pages/search/LocationRadiusPicker.test.tsx`

Expected: PASS with all tests green.

- [ ] **Step 2: Run lint check for UI package**

Run: `npm --prefix apps/ui run lint`

Expected: PASS with no errors.

- [ ] **Step 3: Confirm clean working tree**

Run: `git -C /mnt/d/Projects/photo-org status --short`

Expected: empty output.

- [ ] **Step 4: Create integration commit if verification-only adjustments were needed**

```bash
git -C /mnt/d/Projects/photo-org add -A
git -C /mnt/d/Projects/photo-org commit -m "test: finalize library filter chip popup UX coverage"
```

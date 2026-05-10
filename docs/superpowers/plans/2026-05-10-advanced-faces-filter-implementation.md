# Advanced Faces Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an advanced Library Faces filter with face-count range, top-certainty range, and unknown-person selection, with deterministic UI/URL/API behavior.

**Architecture:** Keep UI interaction state in Library route UI components, URL/request serialization in `libraryRouteSearchState`, request transport in `libraryRouteApi/useLibraryResults`, schema validation in `search_request.py`, and SQL semantics in `photos_repo.py`. Implement face filtering through a new `filters.faces` object without breaking existing search behavior.

**Tech Stack:** React, TypeScript, react-range, Vitest/Testing Library, FastAPI/Pydantic, SQLAlchemy, pytest.

---

## SRP Guardrails

- `LibrarySearchForm.tsx` owns panel orchestration only (open/close/edit flow), not URL parsing.
- Face-filter serialization/parsing lives in `libraryRouteSearchState.ts` only.
- `libraryRouteApi.ts` only sends payloads; no filter business rules.
- `search_request.py` only validates filter schema; no query semantics.
- `photos_repo.py` only expresses query semantics.
- Test files verify observable behavior at each layer and do not duplicate logic from production code.

---

### Task 1: Add API Schema Support For `filters.faces`

**Files:**
- Modify: `apps/api/app/schemas/search_request.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing schema validation tests for faces filter bounds**

```python
def test_faces_filter_validation_rejects_negative_counts():
    with pytest.raises(ValidationError):
        SearchFilters(faces={"min_count": -1})


def test_faces_filter_validation_rejects_invalid_certainty_bounds():
    with pytest.raises(ValidationError):
        SearchFilters(faces={"top_certainty_min": 1.2})


def test_faces_filter_validation_rejects_inverted_ranges():
    with pytest.raises(ValidationError):
        SearchFilters(faces={"min_count": 5, "max_count": 2})
    with pytest.raises(ValidationError):
        SearchFilters(faces={"top_certainty_min": 0.9, "top_certainty_max": 0.1})
```

- [ ] **Step 2: Run tests to verify failure**

Run: `uv run pytest apps/api/tests/test_search_service.py -k "faces_filter_validation"`
Expected: FAIL because `SearchFilters` has no `faces` object yet.

- [ ] **Step 3: Add `FaceFilters` schema model and wire into `SearchFilters`**

```python
class FaceFilters(BaseModel):
    min_count: Optional[int] = Field(default=None, ge=0)
    max_count: Optional[int] = Field(default=None, ge=0)
    top_certainty_min: Optional[float] = None
    top_certainty_max: Optional[float] = None
    has_unknown_person: Optional[bool] = None

    @field_validator("top_certainty_min", "top_certainty_max")
    @classmethod
    def validate_certainty(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if not math.isfinite(value):
            raise ValueError("top certainty bounds must be finite")
        if value < 0 or value > 1:
            raise ValueError("top certainty bounds must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def validate_ranges(self) -> "FaceFilters":
        if self.min_count is not None and self.max_count is not None and self.min_count > self.max_count:
            raise ValueError("min_count must be <= max_count")
        if (
            self.top_certainty_min is not None
            and self.top_certainty_max is not None
            and self.top_certainty_min > self.top_certainty_max
        ):
            raise ValueError("top_certainty_min must be <= top_certainty_max")
        return self
```

- [ ] **Step 4: Add field to `SearchFilters`**

```python
class SearchFilters(BaseModel):
    date: Optional[DateFilter] = None
    camera_make: Optional[List[str]] = None
    extension: Optional[List[str]] = None
    path_hints: Optional[List[str]] = None
    album_ids: Optional[List[str]] = None
    orientation: Optional[List[str]] = None
    filesize_range: Optional[FilesizeRange] = None
    has_faces: Optional[bool] = None
    tags: Optional[List[str]] = None
    people: Optional[List[str]] = None
    person_names: Optional[List[str]] = None
    person_certainty_mode: Optional[Literal["human_only", "include_suggestions"]] = None
    suggestion_confidence_min: Optional[float] = None
    location_radius: Optional[LocationRadiusFilter] = None
    faces: Optional[FaceFilters] = None
```

- [ ] **Step 5: Re-run schema tests**

Run: `uv run pytest apps/api/tests/test_search_service.py -k "faces_filter_validation"`
Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git -C /mnt/d/Projects/photo-org add apps/api/app/schemas/search_request.py apps/api/tests/test_search_service.py
git -C /mnt/d/Projects/photo-org commit -m "feat(api): add faces filter schema validation"
```

---

### Task 2: Implement Repository Query Semantics For Faces Filter

**Files:**
- Modify: `apps/api/app/repositories/photos_repo.py`
- Test: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write failing repository/service tests for face count range**

```python
def test_faces_filter_count_range_filters_results(tmp_path):
    # seed photo-0 (0 active faces), photo-1 (1 active face), photo-2 (2 active faces)
    # assert min_count=1 removes photo-0 and max_count=1 removes photo-2
```

- [ ] **Step 2: Write failing tests for certainty ANY-face semantics and unknown-person filter**

```python
def test_faces_filter_top_certainty_any_face_semantics(tmp_path):
    # photo-a has two faces: one human_confirmed (100%), one top suggestion 0.2
    # photo-b has one face with top suggestion 0.45
    # filter range 0.9..1.0 should include photo-a and exclude photo-b


def test_faces_filter_unknown_person_matches_at_least_one_unknown_assigned_face(tmp_path):
    # photo-u has one face assigned to Unknown person, photo-k has only known assignments
    # has_unknown_person=true should include photo-u and exclude photo-k
```

- [ ] **Step 3: Run targeted tests to verify failure**

Run: `uv run pytest apps/api/tests/test_search_service.py -k "faces_filter_count_range or faces_filter_top_certainty or faces_filter_unknown_person"`
Expected: FAIL before repo logic is added.

- [ ] **Step 4: Add helper clauses in `PhotosRepository` for face filter semantics**

```python
def _active_faces_subquery(self):
    return select(self.faces.c.photo_id, self.faces.c.face_id, self.faces.c.person_id).where(
        self.faces.c.dismissed_ts.is_(None)
    ).subquery()


def _faces_count_clause(self, faces_filter):
    active_face_count = (
        select(func.count())
        .select_from(self.faces)
        .where(
            self.faces.c.photo_id == self.photos.c.photo_id,
            self.faces.c.dismissed_ts.is_(None),
        )
        .scalar_subquery()
    )
    clauses = []
    if faces_filter.min_count is not None:
        clauses.append(active_face_count >= faces_filter.min_count)
    if faces_filter.max_count is not None:
        clauses.append(active_face_count <= faces_filter.max_count)
    return and_(*clauses) if clauses else None


def _faces_top_certainty_clause(self, faces_filter):
    # return EXISTS(correlated_face_query) where any active face for this photo has
    # effective_top_certainty in [top_certainty_min, top_certainty_max]
    # effective_top_certainty = 1.0 for human_confirmed assignment, else top suggestion confidence


def _unknown_person_clause(self, faces_filter):
    # return EXISTS(correlated_unknown_person_query) for at least one active face assigned to a person
    # whose display_name == UNKNOWN_PERSON_DISPLAY_NAME
```

- [ ] **Step 5: Apply faces filter clauses inside `_apply_filters`**

```python
if filters.faces:
    count_clause = self._faces_count_clause(filters.faces)
    if count_clause is not None:
        where_conditions.append(count_clause)
    certainty_clause = self._faces_top_certainty_clause(filters.faces)
    if certainty_clause is not None:
        where_conditions.append(certainty_clause)
    unknown_clause = self._unknown_person_clause(filters.faces)
    if unknown_clause is not None:
        where_conditions.append(unknown_clause)
```

- [ ] **Step 6: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_search_service.py -k "faces_filter_count_range or faces_filter_top_certainty or faces_filter_unknown_person"`
Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git -C /mnt/d/Projects/photo-org add apps/api/app/repositories/photos_repo.py apps/api/tests/test_search_service.py
git -C /mnt/d/Projects/photo-org commit -m "feat(api): implement advanced faces filter query clauses"
```

---

### Task 3: Add UI State Types And URL/Request Serialization Rules

**Files:**
- Modify: `apps/ui/src/pages/library/libraryRouteTypes.ts`
- Modify: `apps/ui/src/pages/library/libraryRouteSearchState.ts`
- Test: `apps/ui/src/pages/library/libraryRouteSearchState.test.ts`

- [ ] **Step 1: Write failing tests for parse/serialize of advanced faces filter**

```ts
it("parses and serializes faces filter params", () => {
  const state = parseLibraryUrlState("?facesMin=2&facesMax=7&facesCertMin=60&facesCertMax=95&facesUnknown=1");
  expect(state.facesFilter).toEqual({
    minCount: 2,
    maxCount: 7,
    certaintyMinPct: 60,
    certaintyMaxPct: 95,
    hasUnknownPerson: true
  });
});

it("omits faces count defaults 0..infinity in URL and payload", () => {
  const query = buildLibraryUrlQuery({
    queryChips: [],
    fromDate: "",
    toDate: "",
    selectedPersonNames: [],
    selectedAlbumIds: [],
    personCertaintyMode: "human_only",
    suggestionConfidenceMinDraft: "0.8",
    locationRadius: null,
    hasFacesFilter: null,
    pathHintFilters: [],
    sortDirection: "desc",
    page: 1,
    pageSize: 60,
    facesFilter: { minCount: 0, maxCount: null, certaintyMinPct: 0, certaintyMaxPct: 100, hasUnknownPerson: false }
  });
  expect(query).not.toContain("facesMin=");
  expect(query).not.toContain("facesMax=");
});

it("omits face-attribute clauses when range is 0..0", () => {
  const filters = buildSearchFilters("", "", [], [], "human_only", "0.8", null, null, [], {
    minCount: 0,
    maxCount: 0,
    certaintyMinPct: 65,
    certaintyMaxPct: 95,
    hasUnknownPerson: true
  });
  expect(filters?.faces).toEqual({ min_count: 0, max_count: 0 });
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- src/pages/library/libraryRouteSearchState.test.ts`
Expected: FAIL (missing facesFilter state/serialization).

- [ ] **Step 3: Add `LibraryFacesFilterState` type and wire into `SearchUrlState`**

```ts
export type LibraryFacesFilterState = {
  minCount: number;
  maxCount: number | null; // null = unbounded
  certaintyMinPct: number;
  certaintyMaxPct: number;
  hasUnknownPerson: boolean;
};
```

- [ ] **Step 4: Implement parse/serialize helpers and request mapping**

```ts
function normalizeFacesFilterForPayload(state: LibraryFacesFilterState): {
  min_count?: number;
  max_count?: number;
  top_certainty_min?: number;
  top_certainty_max?: number;
  has_unknown_person?: boolean;
} | null
```

Rules:
- omit min/max when `0..∞`
- omit certainty/unknown when `0..0`
- convert percent to decimal for request payload

- [ ] **Step 5: Re-run state tests**

Run: `npm --prefix apps/ui test -- src/pages/library/libraryRouteSearchState.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/libraryRouteTypes.ts apps/ui/src/pages/library/libraryRouteSearchState.ts apps/ui/src/pages/library/libraryRouteSearchState.test.ts
git -C /mnt/d/Projects/photo-org commit -m "feat(ui): add advanced faces filter state serialization"
```

---

### Task 4: Wire Advanced Faces Filter Through Request Pipeline

**Files:**
- Modify: `apps/ui/src/pages/library/libraryRouteApi.ts`
- Modify: `apps/ui/src/pages/library/useLibraryResults.ts`
- Modify: `apps/ui/src/pages/LibraryRoutePage.tsx`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Write failing request-payload tests in `LibraryRoutePage.test.tsx`**

```ts
it("sends faces filter payload with count, certainty, and unknown fields", async () => {
  // interact with faces controls
  // assert latest /api/v1/search request body has filters.faces
});

it("suppresses certainty and unknown fields when face count is 0..0", async () => {
  // set 0..0 and assert filters.faces excludes top_certainty_* and has_unknown_person
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- src/pages/LibraryRoutePage.test.tsx -t "faces filter payload"`
Expected: FAIL (payload lacks `filters.faces`).

- [ ] **Step 3: Add faces filter state to route state plumbing**

```ts
const [facesFilter, setFacesFilter] = useState<LibraryFacesFilterState>(parsedUrlState.facesFilter);
```

- [ ] **Step 4: Thread `facesFilter` through `useLibraryResults` and `fetchLibraryPage`**

```ts
fetchLibraryPage(
  committedQuery,
  fromDate,
  toDate,
  selectedPersonNames,
  selectedAlbumIds,
  personCertaintyMode,
  suggestionConfidenceMinDraft,
  locationRadiusFilter,
  hasFacesFilter,
  pathHintFilters,
  facesFilter,
  sortDirection,
  requestOffset,
  pageSize,
  includeFaceInfo
)
```

- [ ] **Step 5: Ensure request body includes `filters.faces` only when active**

```ts
const searchFilters = buildSearchFilters(
  fromDate,
  toDate,
  selectedPersonNames,
  selectedAlbumIds,
  personCertaintyMode,
  suggestionConfidenceMinDraft,
  locationRadius,
  hasFaces,
  pathHints,
  facesFilter
);
```

- [ ] **Step 6: Re-run targeted route tests**

Run: `npm --prefix apps/ui test -- src/pages/LibraryRoutePage.test.tsx -t "faces filter payload|suppresses certainty"`
Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/libraryRouteApi.ts apps/ui/src/pages/library/useLibraryResults.ts apps/ui/src/pages/LibraryRoutePage.tsx apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "feat(ui): wire advanced faces filter into library search requests"
```

---

### Task 5: Build Faces UI Controls With Drag-Stable React-Range Sliders

**Files:**
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Modify: `apps/ui/src/pages/shared/ConfidenceSlider.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`

- [ ] **Step 1: Write failing UI tests for Faces panel controls**

```ts
it("renders faces range sliders and unknown checkbox in faces panel", async () => {
  await user.click(screen.getByRole("button", { name: "Faces filter type" }));
  expect(screen.getByText("Face count range")).toBeInTheDocument();
  expect(screen.getByText("Top certainty range")).toBeInTheDocument();
  expect(screen.getByRole("checkbox", { name: "Has face assigned to unknown person" })).toBeInTheDocument();
});

it("shows infinity label when max faces handle is 10", async () => {
  await user.click(screen.getByRole("button", { name: "Faces filter type" }));
  expect(screen.getByText(/At most faces: ∞/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm --prefix apps/ui test -- src/pages/LibraryRoutePage.test.tsx -t "faces panel controls|infinity label"`
Expected: FAIL (controls not present yet).

- [ ] **Step 3: Extend slider component support for custom bounds/labels**

```ts
interface ConfidenceRangeSliderProps {
  minValue: number;
  maxValue: number;
  onValueChange: (minValue: number, maxValue: number) => void;
  disabled?: boolean;
  minBound?: number;
  maxBound?: number;
  minLabel?: string;
  maxLabel?: string;
  maxValueFormatter?: (value: number) => string;
}
```

Keep `onChange` draft state + `onFinalChange` commit behavior to retain smooth dragging.

- [ ] **Step 4: Implement Faces panel in `LibrarySearchForm.tsx`**

```tsx
<button aria-label="Faces filter type">Faces</button>
<ConfidenceRangeSlider
  minBound={0}
  maxBound={10}
  minLabel="At least faces"
  maxLabel="At most faces"
  maxValueFormatter={(value) => (value === 10 ? "∞" : String(value))}
  minValue={facesFilter.minCount}
  maxValue={facesFilter.maxCount ?? 10}
  onValueChange={onFacesCountRangeChange}
/>
<ConfidenceRangeSlider
  minBound={0}
  maxBound={100}
  minLabel="Top certainty minimum"
  maxLabel="Top certainty maximum"
  minValue={facesFilter.certaintyMinPct}
  maxValue={facesFilter.certaintyMaxPct}
  disabled={isZeroFacesOnly}
  onValueChange={onFacesCertaintyRangeChange}
/>
<label className="search-filter-checkbox-row">
  <input
    type="checkbox"
    checked={facesFilter.hasUnknownPerson}
    disabled={isZeroFacesOnly}
    onChange={(event) => onFacesUnknownToggle(event.target.checked)}
  />
  Has face assigned to unknown person
</label>
```

- [ ] **Step 5: Add/adjust styles for Faces panel rows and helper text**

```css
.search-faces-panel {
  display: grid;
  gap: 0.55rem;
}

.search-faces-helper-text {
  margin: 0;
  color: #64748b;
  font-size: 0.88rem;
}

.search-filter-checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #334155;
}
```

- [ ] **Step 6: Re-run targeted UI tests**

Run: `npm --prefix apps/ui test -- src/pages/LibraryRoutePage.test.tsx -t "faces panel controls|infinity label|faces filter payload"`
Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git -C /mnt/d/Projects/photo-org add apps/ui/src/pages/library/LibrarySearchForm.tsx apps/ui/src/pages/shared/ConfidenceSlider.tsx apps/ui/src/styles/app-shell.css apps/ui/src/pages/LibraryRoutePage.test.tsx
git -C /mnt/d/Projects/photo-org commit -m "feat(ui): add advanced faces filter panel with range sliders"
```

---

### Task 6: Full Verification Pass

**Files:**
- Verify only; no planned file creation.

- [ ] **Step 1: Run UI tests for touched files**

Run: `npm --prefix apps/ui test -- src/pages/LibraryRoutePage.test.tsx src/pages/library/libraryRouteSearchState.test.ts src/pages/search/LocationRadiusPicker.test.tsx`
Expected: PASS.

- [ ] **Step 2: Run API tests for search filter behavior**

Run: `uv run pytest apps/api/tests/test_search_service.py -k "faces_filter or location_radius or page_spec"`
Expected: PASS.

- [ ] **Step 3: Run UI build check**

Run: `npm --prefix apps/ui run build`
Expected: PASS (or known unrelated failure documented before merge).

- [ ] **Step 4: Confirm working tree and summarize residual risks**

Run: `git -C /mnt/d/Projects/photo-org status --short`
Expected: empty output.

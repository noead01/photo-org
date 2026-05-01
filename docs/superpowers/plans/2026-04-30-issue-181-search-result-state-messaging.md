# Issue #181 Search Result State Messaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement explicit `/search` empty vs no-match vs error messaging with deterministic retry replay and preserved filter context.

**Architecture:** Keep behavior local to `SearchRoutePage` by introducing derived result-state classification and immutable request snapshots for retry replay. Avoid backend/schema changes and keep existing query/filter URL sync model unchanged.

**Tech Stack:** React, TypeScript, Vitest, Testing Library

---

### Task 1: Lock issue #181 behavior with failing UI tests

**Files:**
- Modify: `apps/ui/src/pages/SearchRoutePage.test.tsx`

- [ ] **Step 1: Add failing test for baseline empty state distinct from no-match**

```tsx
it("renders baseline empty state when zero hits are returned without active query filters", async () => {
  const user = userEvent.setup();
  let searchRequestCount = 0;

  fetchMock.mockImplementation(async (input: string) => {
    if (input === PEOPLE_ENDPOINT) {
      return { ok: true, json: async () => PEOPLE_FIXTURE } as Response;
    }
    searchRequestCount += 1;
    return {
      ok: true,
      json: async () => buildPayload([], 0)
    } as Response;
  });

  renderSearchAt();

  const input = await screen.findByRole("textbox", { name: "Search query" });
  await user.type(input, "lake");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await user.click(screen.getByRole("button", { name: "Remove query lake" }));

  expect(await screen.findByText("No photos are available in the catalog yet.")).toBeInTheDocument();
  expect(screen.queryByText("No matching photos for the active query.")).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Add failing test that Retry replays exact failed payload snapshot**

```tsx
it("retries with the exact last failed request payload even after draft edits", async () => {
  const user = userEvent.setup();
  let searchRequestCount = 0;

  fetchMock.mockImplementation(async (input: string) => {
    if (input === PEOPLE_ENDPOINT) {
      return { ok: true, json: async () => PEOPLE_FIXTURE } as Response;
    }

    searchRequestCount += 1;
    if (searchRequestCount === 1) {
      return { ok: false, status: 503 } as Response;
    }

    return {
      ok: true,
      json: async () => buildPayload(["photo-1"], 1)
    } as Response;
  });

  renderSearchAt();

  const queryInput = await screen.findByRole("textbox", { name: "Search query" });
  await user.type(queryInput, "storm coast");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await screen.findByRole("heading", { name: "Could not load Search", level: 2 });

  await user.type(queryInput, " replacement draft");
  await user.type(screen.getByLabelText("From date"), "2026-04-01");

  await user.click(screen.getByRole("button", { name: "Retry" }));

  const body = lastSearchBody(fetchMock);
  expect(body.q).toBe("storm coast");
  expect(body.filters).toBeUndefined();
});
```

- [ ] **Step 3: Run focused tests and verify they fail for expected reason**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx -t "baseline empty state|exact last failed request payload"`

Expected: FAIL because current component has one generic zero-result message and retry reads live current state rather than frozen failed snapshot.

- [ ] **Step 4: Commit failing test changes**

```bash
git add apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "test(ui): lock search result state messaging and retry replay behavior"
```

### Task 2: Implement result-state classification and deterministic retry snapshot

**Files:**
- Modify: `apps/ui/src/pages/SearchRoutePage.tsx`
- Test: `apps/ui/src/pages/SearchRoutePage.test.tsx`

- [ ] **Step 1: Add request snapshot and active-criteria helpers in SearchRoutePage**

```tsx
type SearchRequestSnapshot = {
  chips: string[];
  fromDate: string;
  toDate: string;
  personNames: string[];
  locationRadius: { latitude: number; longitude: number; radius_km: number } | null;
  hasFaces: boolean | null;
  pathHints: string[];
  sortDirection: SortDirection;
  page: number;
  cursorByPage: Record<number, string | null>;
};

function hasActiveSearchCriteria(snapshot: SearchRequestSnapshot): boolean {
  return (
    snapshot.chips.length > 0 ||
    Boolean(snapshot.fromDate || snapshot.toDate) ||
    snapshot.personNames.length > 0 ||
    snapshot.locationRadius !== null ||
    snapshot.hasFaces !== null ||
    snapshot.pathHints.length > 0
  );
}
```

- [ ] **Step 2: Refactor request execution to run from immutable snapshot and store failed snapshot**

```tsx
const [lastFailedRequest, setLastFailedRequest] = useState<SearchRequestSnapshot | null>(null);
const [lastSuccessfulHadCriteria, setLastSuccessfulHadCriteria] = useState(false);

function handleRetry() {
  if (lastFailedRequest) {
    void runSearch(lastFailedRequest);
    return;
  }
  requestSearch();
}
```

- [ ] **Step 3: Set success/error state transitions and render empty vs no-match messaging**

```tsx
const resultViewState = useMemo(() => {
  if (isLoading) return "loading";
  if (error) return "error";
  if (!hasRequested) return "idle";
  if (results.length > 0) return "results";
  return lastSuccessfulHadCriteria ? "no_match" : "empty";
}, [error, hasRequested, isLoading, lastSuccessfulHadCriteria, results.length]);
```

```tsx
{resultViewState === "empty" ? (
  <div className="feedback-panel">
    <p>No photos are available in the catalog yet.</p>
  </div>
) : null}

{resultViewState === "no_match" ? (
  <div className="feedback-panel">
    <p>No matching photos for the active query.</p>
  </div>
) : null}
```

- [ ] **Step 4: Run focused test slice and verify it passes**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx -t "baseline empty state|exact last failed request payload|loading status while the search request is pending|shows retry UI on failure and retries with active chips"`

Expected: PASS with distinct empty/no-match messaging and retry payload replay locked.

- [ ] **Step 5: Commit implementation changes**

```bash
git add apps/ui/src/pages/SearchRoutePage.tsx apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "feat(ui): add explicit search result states and deterministic retry replay"
```

### Task 3: Run full search-route verification and finalize issue #181

**Files:**
- Modify (if needed): `apps/ui/src/pages/SearchRoutePage.tsx`
- Modify (if needed): `apps/ui/src/pages/SearchRoutePage.test.tsx`

- [ ] **Step 1: Run full SearchRoutePage suite**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx`

Expected: PASS with no regressions in existing query chips, filter payloads, URL sync, pagination behavior.

- [ ] **Step 2: Run broader UI safety check touching search route dependencies**

Run: `npm --prefix apps/ui test -- src/pages/SearchRoutePage.test.tsx src/pages/BrowseRoutePage.test.tsx src/app/AppShell.test.tsx`

Expected: PASS ensuring shared feedback/state patterns remain stable.

- [ ] **Step 3: Inspect diff scope**

Run: `git status --short`

Expected: only `SearchRoutePage` and its test updates related to issue `#181`.

- [ ] **Step 4: Commit final polish if additional edits were required**

```bash
git add apps/ui/src/pages/SearchRoutePage.tsx apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "test(ui): verify search result messaging state transitions"
```

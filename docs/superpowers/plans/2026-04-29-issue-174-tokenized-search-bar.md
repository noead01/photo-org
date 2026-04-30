# Issue #174 Tokenized Search Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `/search` route text-query workflow with phrase chips, deterministic submit/clear behavior, and route-local loading/error/empty/success states against `/api/v1/search`.

**Architecture:** Introduce a dedicated `SearchRoutePage` component and route `/search` to it from `AppRouter`. Keep all #174 logic local to this page (state, query-chip interactions, fetch lifecycle) and avoid URL-sync work reserved for #179. Use explicit test-first slices so submit, chip-dismiss clear, and request serialization are all proven deterministic.

**Tech Stack:** React 18, React Router 6, TypeScript, Vitest, Testing Library, existing app-shell CSS.

---

## File Structure And Ownership

- Create: `apps/ui/src/pages/SearchRoutePage.tsx`
- Create: `apps/ui/src/pages/SearchRoutePage.test.tsx`
- Modify: `apps/ui/src/app/AppRouter.tsx`
- Modify: `apps/ui/src/app/AppShell.test.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- External follow-up tracking (post-implementation): GitHub issue in `noead01/photo-org` for shared browse/search refactor story

`SearchRoutePage.tsx` owns route-local query chips, submit/dismiss handlers, and search request lifecycle. `SearchRoutePage.test.tsx` owns interaction and state determinism coverage for #174 acceptance criteria.

### Task 1: Create Search Route Tests For Phrase Submit And Whitespace No-Op

**Files:**
- Create: `apps/ui/src/pages/SearchRoutePage.test.tsx`

- [ ] **Step 1: Write failing tests for submit interactions and request mapping**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SearchRoutePage } from "./SearchRoutePage";

function renderSearchAt(path = "/search") {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/search" element={<SearchRoutePage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("SearchRoutePage", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ hits: { total: 0, cursor: null, items: [] }, facets: {} })
    } as Response);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a phrase chip with Enter and sends q using chip-order serialization", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "lake weekend{enter}");

    expect(await screen.findByRole("button", { name: "Remove query lake weekend" })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalled();

    const lastCall = fetchMock.mock.calls.at(-1);
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("lake weekend");
    expect(body.sort).toEqual({ by: "shot_ts", dir: "desc" });
    expect(body.page).toEqual({ limit: 24, cursor: null });
  });

  it("submits with Search button and appends phrase as a new chip", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "first phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await user.type(input, "second phrase");
    await user.click(screen.getByRole("button", { name: "Search" }));

    expect(screen.getByRole("button", { name: "Remove query first phrase" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove query second phrase" })).toBeInTheDocument();

    const lastCall = fetchMock.mock.calls.at(-1);
    const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
    expect(body.q).toBe("first phrase second phrase");
  });

  it("ignores whitespace-only submit and keeps existing chips and request count unchanged", async () => {
    const user = userEvent.setup();
    renderSearchAt();

    const input = await screen.findByRole("textbox", { name: "Search query" });
    await user.type(input, "coastline");
    await user.click(screen.getByRole("button", { name: "Search" }));
    const callsAfterFirstSubmit = fetchMock.mock.calls.length;

    await user.clear(input);
    await user.type(input, "   ");
    await user.keyboard("{Enter}");

    expect(fetchMock.mock.calls.length).toBe(callsAfterFirstSubmit);
    expect(screen.getByRole("button", { name: "Remove query coastline" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx`
Expected: FAIL with module/file-not-found for `SearchRoutePage`.

- [ ] **Step 3: Commit the failing test scaffold**

```bash
git add apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "test(ui): add failing search route phrase-submit specs"
```

### Task 2: Implement Base SearchRoutePage For Submit, Chips, And Request Serialization

**Files:**
- Create: `apps/ui/src/pages/SearchRoutePage.tsx`

- [ ] **Step 1: Add minimal implementation to satisfy Task 1 tests**

```tsx
import { FormEvent, useState } from "react";

type SearchPhoto = {
  photo_id: string;
  path: string;
  ext: string;
  shot_ts: string | null;
  filesize: number;
};

type SearchResponsePayload = {
  hits: {
    total: number;
    cursor: string | null;
    items: SearchPhoto[];
  };
};

const DEFAULT_SORT = { by: "shot_ts", dir: "desc" } as const;
const DEFAULT_PAGE = { limit: 24, cursor: null } as const;

async function fetchSearchResults(query: string): Promise<SearchResponsePayload> {
  const response = await fetch("/api/v1/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ q: query, sort: DEFAULT_SORT, page: DEFAULT_PAGE })
  });

  if (!response.ok) {
    throw new Error(`Search request failed (${response.status})`);
  }

  return (await response.json()) as SearchResponsePayload;
}

export function SearchRoutePage() {
  const [draftQuery, setDraftQuery] = useState("");
  const [queryChips, setQueryChips] = useState<string[]>([]);
  const [results, setResults] = useState<SearchPhoto[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSearch(chips: string[]) {
    setIsLoading(true);
    setError(null);
    try {
      const payload = await fetchSearchResults(chips.join(" "));
      setResults(payload.hits.items);
      setTotalCount(payload.hits.total);
    } catch (caughtError: unknown) {
      setError(caughtError instanceof Error ? caughtError.message : "Could not load search results.");
    } finally {
      setIsLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = draftQuery.trim();
    if (!trimmed) {
      return;
    }

    const nextChips = [...queryChips, trimmed];
    setQueryChips(nextChips);
    setDraftQuery("");
    void runSearch(nextChips);
  }

  return (
    <section aria-labelledby="page-title" className="page search-page">
      <h1 id="page-title">Search</h1>
      <p>Build text-query chips for deterministic search submissions.</p>

      <form className="search-query-form" onSubmit={handleSubmit}>
        <label htmlFor="search-query-input">Search query</label>
        <div className="search-query-row">
          <input
            id="search-query-input"
            type="text"
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
          />
          <button type="submit">Search</button>
        </div>
      </form>

      <ul className="search-chip-list" aria-label="Active query filters">
        {queryChips.map((chip, index) => (
          <li key={`${chip}-${index}`}>
            <button type="button" aria-label={`Remove query ${chip}`}>{chip} ×</button>
          </li>
        ))}
      </ul>

      <p className="search-summary" aria-live="polite">
        {isLoading ? "Loading search workflow." : `Showing ${results.length} of ${totalCount} photos`}
      </p>

      {error ? (
        <div className="feedback-panel feedback-panel-error">
          <h2>Could not load Search</h2>
          <p>{error}</p>
        </div>
      ) : null}

      {!error && !isLoading && results.length === 0 ? (
        <div className="feedback-panel">
          <p>No matching photos for the active query.</p>
        </div>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 2: Run targeted tests and verify Task 1 tests pass**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx`
Expected: PASS for submit and whitespace no-op coverage.

- [ ] **Step 3: Commit implementation slice**

```bash
git add apps/ui/src/pages/SearchRoutePage.tsx
git commit -m "feat(ui): add search route phrase submit and serialization behavior"
```

### Task 3: Add Chip Dismiss Clear And Deterministic Re-fetch

**Files:**
- Modify: `apps/ui/src/pages/SearchRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/SearchRoutePage.tsx`

- [ ] **Step 1: Add failing dismiss-chip test**

```tsx
it("removes dismissed chip and re-fetches using remaining chip order", async () => {
  const user = userEvent.setup();
  renderSearchAt();

  const input = await screen.findByRole("textbox", { name: "Search query" });
  await user.type(input, "alpha");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await user.type(input, "beta");
  await user.click(screen.getByRole("button", { name: "Search" }));

  await user.click(screen.getByRole("button", { name: "Remove query alpha" }));

  const lastCall = fetchMock.mock.calls.at(-1);
  const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
  expect(body.q).toBe("beta");
  expect(screen.queryByRole("button", { name: "Remove query alpha" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Remove query beta" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to confirm failure**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx -t "removes dismissed chip"`
Expected: FAIL because dismiss handler is missing.

- [ ] **Step 3: Implement dismiss behavior in the component**

```tsx
function handleDismissChip(indexToRemove: number) {
  const nextChips = queryChips.filter((_, index) => index !== indexToRemove);
  setQueryChips(nextChips);
  void runSearch(nextChips);
}

// In chip render:
<button
  type="button"
  aria-label={`Remove query ${chip}`}
  onClick={() => handleDismissChip(index)}
>
  {chip} ×
</button>
```

- [ ] **Step 4: Run targeted test file and verify pass**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx`
Expected: PASS including dismiss-chip scenario.

- [ ] **Step 5: Commit chip-dismiss slice**

```bash
git add apps/ui/src/pages/SearchRoutePage.tsx apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "feat(ui): support chip-dismiss clear and deterministic re-query"
```

### Task 4: Add Loading, Error Retry, Empty, And Success State Coverage

**Files:**
- Modify: `apps/ui/src/pages/SearchRoutePage.test.tsx`
- Modify: `apps/ui/src/pages/SearchRoutePage.tsx`

- [ ] **Step 1: Add failing tests for loading, error retry, and empty state**

```tsx
it("renders loading status while the search request is pending", async () => {
  let resolveResponse: ((value: Response) => void) | null = null;
  fetchMock.mockImplementationOnce(
    () =>
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      })
  );

  const user = userEvent.setup();
  renderSearchAt();

  const input = await screen.findByRole("textbox", { name: "Search query" });
  await user.type(input, "harbor");
  await user.keyboard("{Enter}");

  expect(screen.getByRole("status")).toHaveTextContent("Loading search workflow.");

  resolveResponse?.({
    ok: true,
    json: async () => ({ hits: { total: 0, cursor: null, items: [] }, facets: {} })
  } as Response);
});

it("shows retry UI on failure and retries with active chips", async () => {
  const user = userEvent.setup();
  fetchMock
    .mockResolvedValueOnce({ ok: false, status: 503 } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        hits: {
          total: 1,
          cursor: null,
          items: [{ photo_id: "photo-1", path: "/library/photo-1.jpg", ext: "jpg", shot_ts: null, filesize: 1024 }]
        },
        facets: {}
      })
    } as Response);

  renderSearchAt();
  const input = await screen.findByRole("textbox", { name: "Search query" });
  await user.type(input, "storm coast");
  await user.click(screen.getByRole("button", { name: "Search" }));

  expect(await screen.findByRole("heading", { name: "Could not load Search", level: 2 })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Retry" }));

  const lastCall = fetchMock.mock.calls.at(-1);
  const body = JSON.parse(String((lastCall?.[1] as RequestInit).body));
  expect(body.q).toBe("storm coast");
  expect(await screen.findByText("photo-1")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx -t "retry UI|loading status"`
Expected: FAIL due missing retry handler and missing status semantics.

- [ ] **Step 3: Implement state panels and retry handler**

```tsx
async function runSearch(chips: string[]) {
  setIsLoading(true);
  setError(null);
  try {
    const payload = await fetchSearchResults(chips.join(" "));
    setResults(payload.hits.items);
    setTotalCount(payload.hits.total);
  } catch (caughtError: unknown) {
    const message = caughtError instanceof Error ? caughtError.message : "Could not load search results.";
    setError(message);
    setResults([]);
    setTotalCount(0);
  } finally {
    setIsLoading(false);
  }
}

function handleRetry() {
  void runSearch(queryChips);
}

{isLoading ? (
  <div className="feedback-panel feedback-panel-loading" role="status" aria-live="polite">
    Loading search workflow.
  </div>
) : null}

{error ? (
  <div className="feedback-panel feedback-panel-error">
    <h2>Could not load Search</h2>
    <p>{error}</p>
    <button type="button" onClick={handleRetry}>Retry</button>
  </div>
) : null}

{!error && !isLoading && results.length > 0 ? (
  <ol className="search-results" aria-label="Search results">
    {results.map((photo) => (
      <li key={photo.photo_id}>
        <h2>{photo.photo_id}</h2>
        <p>{photo.path}</p>
      </li>
    ))}
  </ol>
) : null}
```

- [ ] **Step 4: Run full SearchRoutePage test file**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx`
Expected: PASS with loading, error retry, empty, and success coverage.

- [ ] **Step 5: Commit feedback-state slice**

```bash
git add apps/ui/src/pages/SearchRoutePage.tsx apps/ui/src/pages/SearchRoutePage.test.tsx
git commit -m "feat(ui): add search route loading error retry and result states"
```

### Task 5: Route Integration And Shell Test Updates

**Files:**
- Modify: `apps/ui/src/app/AppRouter.tsx`
- Modify: `apps/ui/src/app/AppShell.test.tsx`

- [ ] **Step 1: Add failing shell test that expects search controls on `/search`**

```tsx
it("renders search query controls on the /search route", async () => {
  renderAtPath("/search");

  expect(await screen.findByRole("heading", { name: "Search", level: 1 })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Search query" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run shell tests and verify failure**

Run: `npm --prefix apps/ui run test -- src/app/AppShell.test.tsx -t "renders search query controls"`
Expected: FAIL because `/search` still renders `PrimaryRoutePage`.

- [ ] **Step 3: Wire `/search` route to `SearchRoutePage`**

```tsx
import { SearchRoutePage } from "../pages/SearchRoutePage";

// Inside route map element selection:
route.key === "browse" ? (
  <BrowseRoutePage />
) : route.key === "search" ? (
  <SearchRoutePage />
) : (
  <PrimaryRoutePage route={route} />
)
```

- [ ] **Step 4: Run shell and search page tests together**

Run: `npm --prefix apps/ui run test -- src/app/AppShell.test.tsx src/pages/SearchRoutePage.test.tsx`
Expected: PASS for route integration and search interactions.

- [ ] **Step 5: Commit router integration slice**

```bash
git add apps/ui/src/app/AppRouter.tsx apps/ui/src/app/AppShell.test.tsx
git commit -m "feat(ui): route /search to dedicated search workflow page"
```

### Task 6: Add Search-Page Styles For Chips And Result Layout

**Files:**
- Modify: `apps/ui/src/styles/app-shell.css`

- [ ] **Step 1: Add search page CSS blocks**

```css
.search-page {
  display: grid;
  gap: 0.9rem;
}

.search-query-form {
  display: grid;
  gap: 0.35rem;
}

.search-query-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.search-query-row input {
  flex: 1 1 16rem;
  min-width: 12rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.45rem;
  padding: 0.45rem 0.55rem;
  font: inherit;
}

.search-query-row button {
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 0.45rem;
  padding: 0.45rem 0.7rem;
  font: inherit;
}

.search-chip-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.search-chip-list button {
  border: 1px solid #bfdbfe;
  background: #f8fbff;
  color: #1e3a8a;
  border-radius: 999px;
  padding: 0.3rem 0.6rem;
  font: inherit;
}

.search-results {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.6rem;
}

.search-results li {
  border: 1px solid #dbe4ee;
  border-radius: 0.55rem;
  background: #ffffff;
  padding: 0.65rem 0.75rem;
}

@media (max-width: 640px) {
  .search-query-row {
    flex-direction: column;
  }

  .search-query-row button {
    width: fit-content;
  }
}
```

- [ ] **Step 2: Run search-focused test file after CSS changes**

Run: `npm --prefix apps/ui run test -- src/pages/SearchRoutePage.test.tsx`
Expected: PASS (CSS-only changes should not alter behavior).

- [ ] **Step 3: Commit style slice**

```bash
git add apps/ui/src/styles/app-shell.css
git commit -m "style(ui): add search route query chip and result layout styles"
```

### Task 7: Full Verification For #174 Scope

**Files:**
- Verify behavior in modified UI tests

- [ ] **Step 1: Run all unit tests in UI package**

Run: `npm --prefix apps/ui run test`
Expected: PASS with no failing test files.

- [ ] **Step 2: Run TypeScript build for UI package**

Run: `npm --prefix apps/ui run build`
Expected: PASS with successful `tsc -b` and `vite build` output.

- [ ] **Step 3: Manual local smoke check for route behavior**

Run: `npm --prefix apps/ui run dev`
Expected: `/search` supports Enter + Search submit, whitespace no-op, multi-chip accumulation, chip-dismiss re-query, and retry flow.

- [ ] **Step 4: Create a verification commit only if Step 1-3 required code/test updates**

```bash
git add -A
git commit -m "test(ui): finalize issue #174 verification adjustments"
```

### Task 8: Create Follow-Up Refactor Story (Post-#174)

**Files:**
- External write: GitHub issue in `noead01/photo-org`

- [ ] **Step 1: Create a new UI implementation story for shared browse/search refactor**

Issue title:

`Refactor shared browse-search request lifecycle and result rendering primitives`

Issue body sections:

- Summary: extract shared request-state handling from `BrowseRoutePage` and `SearchRoutePage`
- Scope:
  - shared request lifecycle hook for loading/error/retry/state reset
  - shared result card/list primitives where responsibilities overlap
  - shared query serialization helpers for upcoming #175-#181
- Non-Goals:
  - behavior changes to #174 chip semantics
  - URL sync work owned by #179
- Dependencies: reference #174, #175-#181, #179

- [ ] **Step 2: Link the follow-up issue in #174 comments**

Comment text:

`Tracking follow-up refactor work separately to keep #174 focused on deterministic tokenized search interactions.`

- [ ] **Step 3: No code commit needed for external issue management task**

## Self-Review Checklist

- Spec coverage:
  - submit interactions (Enter + button): Tasks 1-2
  - phrase chip model and multi-chip serialization: Tasks 1-3
  - chip dismiss clear: Task 3
  - empty/invalid whitespace no-op: Task 1
  - loading/error/empty/success states: Task 4
  - route integration on `/search`: Task 5
  - deferred refactor story: Task 8
- Placeholder scan:
  - no TBD/TODO/fill-later text in execution steps
  - all commands and expected outcomes included
- Type consistency:
  - `queryChips`, `draftQuery`, `SearchRoutePage`, `/api/v1/search`, `q` naming held constant across tasks

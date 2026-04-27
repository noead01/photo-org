# UI Testing Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved Approach C UI testing strategy by adding Playwright E2E automation, journey AC documentation, traceability mapping, and CI lanes (`ui-unit`, `ui-e2e-smoke`, `ui-e2e-full`).

**Architecture:** Keep executable UI tests in Playwright under `apps/ui/tests/e2e` and keep business-readable acceptance criteria in non-executable journey docs under `docs/testing/journeys`. Use tags (`@smoke`, `@journey`, `@technical`, `@quarantine`) to control CI lane scope and preserve the PR runtime budget.

**Tech Stack:** React + Vite, Vitest, Playwright, GitHub Actions, Markdown docs

---

## File Structure And Ownership

**Create:**

- `apps/ui/playwright.config.ts`
  Playwright runtime config, server boot, reporter, retries, and project setup.
- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
  Journey-level smoke tests tied to Phase 2 and Phase 3 shell/navigation outcomes.
- `apps/ui/tests/e2e/technical/navigation-state.spec.ts`
  Technical E2E checks for deep links, browser history, and URL/query behavior.
- `apps/ui/tests/e2e/support/navAsserts.ts`
  Shared assertion helper for active primary navigation state.
- `docs/testing/journeys/_template.md`
  Journey AC template for shared product/QA/engineering authoring.
- `docs/testing/journeys/JRN-P2-shell-navigation-continuity.md`
  Approved journey AC document for shell continuity.
- `docs/testing/journeys/JRN-P2-not-found-recovery.md`
  Approved journey AC document for 404 recovery through primary navigation.
- `docs/testing/journeys/JRN-P3-search-route-deep-link.md`
  Approved journey AC document for deep-linking directly into search.
- `docs/testing/journey-traceability.md`
  Journey-to-test-to-issue mapping source of truth.
- `.github/workflows/ui-tests.yml`
  CI workflow implementing required PR and non-blocking full lanes.
- `.github/pull_request_template.md`
  Pull request checklist requiring impacted journey IDs.

**Modify:**

- `apps/ui/package.json`
  Add Playwright dependency and E2E scripts with tag-based entry points.
- `apps/ui/package-lock.json`
  Lockfile update after adding Playwright.
- `.gitignore`
  Ignore Playwright HTML report and test result artifacts.
- `CONTRIBUTING.md`
  Add UI test commands and journey documentation workflow guidance.

No app runtime behavior changes are required for this plan.

### Task 1: Bootstrap Playwright With Journey Smoke Coverage

**Files:**
- Create: `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
- Modify: `apps/ui/package.json`
- Modify: `apps/ui/package-lock.json`
- Create: `apps/ui/playwright.config.ts`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing journey smoke test file first**

Create `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts` with:

```ts
import { expect, test } from "@playwright/test";

test("JRN-P2-shell-navigation-continuity @journey @smoke", async ({ page }) => {
  await page.goto("/browse");

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "browse");
  await expect(page.getByRole("heading", { level: 1, name: "Browse" })).toBeVisible();

  await page.getByRole("link", { name: "Search" }).click();

  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "search");
  await expect(page.getByRole("heading", { level: 1, name: "Search" })).toBeVisible();
});

test("JRN-P2-not-found-recovery @journey @smoke", async ({ page }) => {
  await page.goto("/does-not-exist");

  await expect(page.getByRole("heading", { level: 1, name: "Page Not Found" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();

  await page.getByRole("link", { name: "Browse" }).click();
  await expect(page).toHaveURL(/\/browse$/);
  await expect(page.getByRole("heading", { level: 1, name: "Browse" })).toBeVisible();
});

test("JRN-P3-search-route-deep-link @journey @smoke", async ({ page }) => {
  await page.goto("/search");

  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "search");
  await expect(page.getByRole("heading", { level: 1, name: "Search" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Search" })).toHaveAttribute(
    "aria-current",
    "page"
  );
});
```

- [ ] **Step 2: Run the smoke command and verify it fails before tooling exists**

Run:

```bash
cd apps/ui
npm run test:e2e:smoke
```

Expected: command fails with `Missing script: "test:e2e:smoke"`.

- [ ] **Step 3: Add Playwright dependency and scripts**

Update `apps/ui/package.json` scripts and dev dependencies to:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "test:e2e:smoke": "playwright test --grep @smoke",
    "test:e2e:full": "playwright test --grep-invert @quarantine",
    "test:e2e:journey": "playwright test --grep @journey",
    "test:e2e:technical": "playwright test --grep @technical",
    "test:e2e:report": "playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.55.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.1",
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.4.1",
    "jsdom": "^24.1.3",
    "typescript": "^5.8.3",
    "vite": "^5.4.19",
    "vitest": "^1.6.1"
  }
}
```

Then run:

```bash
cd apps/ui
npm install
```

Expected: `apps/ui/package-lock.json` updates and lockfile includes `@playwright/test`.

- [ ] **Step 4: Add Playwright configuration**

Create `apps/ui/playwright.config.ts` with:

```ts
import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:4173";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: {
    timeout: 5_000
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI
    ? [["github"], ["list"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure"
  },
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 4173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: baseURL
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"]
      }
    }
  ]
});
```

- [ ] **Step 5: Ignore Playwright output artifacts**

Append to `.gitignore`:

```gitignore
apps/ui/playwright-report/
apps/ui/test-results/
```

- [ ] **Step 6: Run smoke tests and verify pass**

Run:

```bash
cd apps/ui
npx playwright install --with-deps chromium
npm run test:e2e:smoke
```

Expected: all three smoke journey tests pass in Chromium.

- [ ] **Step 7: Commit Task 1**

```bash
git add apps/ui/package.json apps/ui/package-lock.json apps/ui/playwright.config.ts apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts .gitignore
git commit -m "test(ui): add playwright smoke journeys and baseline config"
```

### Task 2: Add Technical E2E Coverage And Shared Assertion Helper

**Files:**
- Create: `apps/ui/tests/e2e/technical/navigation-state.spec.ts`
- Create: `apps/ui/tests/e2e/support/navAsserts.ts`

- [ ] **Step 1: Write technical tests that fail due missing shared helper**

Create `apps/ui/tests/e2e/technical/navigation-state.spec.ts` with:

```ts
import { expect, test } from "@playwright/test";
import { expectPrimaryLinkActive } from "../support/navAsserts";

test("technical: deep-link query state renders expected route shell @technical", async ({
  page
}) => {
  await page.goto("/search?query=lake");

  await expect(page).toHaveURL(/\/search\?query=lake$/);
  await expect(page.locator(".app-shell")).toHaveAttribute("data-shell-route", "search");
  await expectPrimaryLinkActive(page, "Search");
});

test("technical: browser back and forward keep shell mounted with route-local content @technical", async ({
  page
}) => {
  await page.goto("/browse");
  await page.getByRole("link", { name: "Operations" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Operations" })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole("heading", { level: 1, name: "Browse" })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole("heading", { level: 1, name: "Operations" })).toBeVisible();
  await expect(page.getByRole("banner")).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Primary" })).toBeVisible();
});
```

- [ ] **Step 2: Run technical tests and verify they fail**

Run:

```bash
cd apps/ui
npm run test:e2e:technical
```

Expected: TypeScript/loader failure because `../support/navAsserts` does not exist.

- [ ] **Step 3: Add shared navigation assertion helper**

Create `apps/ui/tests/e2e/support/navAsserts.ts` with:

```ts
import { expect, type Page } from "@playwright/test";

export async function expectPrimaryLinkActive(page: Page, label: string): Promise<void> {
  await expect(
    page.getByRole("link", {
      name: label
    })
  ).toHaveAttribute("aria-current", "page");
}
```

- [ ] **Step 4: Run technical tests and full E2E lane**

Run:

```bash
cd apps/ui
npm run test:e2e:technical
npm run test:e2e:full
```

Expected: technical tests pass and full lane passes without quarantined tests.

- [ ] **Step 5: Commit Task 2**

```bash
git add apps/ui/tests/e2e/technical/navigation-state.spec.ts apps/ui/tests/e2e/support/navAsserts.ts
git commit -m "test(ui): add technical e2e coverage for route and history behavior"
```

### Task 3: Add Journey AC Documents And Traceability Mapping

**Files:**
- Create: `docs/testing/journeys/_template.md`
- Create: `docs/testing/journeys/JRN-P2-shell-navigation-continuity.md`
- Create: `docs/testing/journeys/JRN-P2-not-found-recovery.md`
- Create: `docs/testing/journeys/JRN-P3-search-route-deep-link.md`
- Create: `docs/testing/journey-traceability.md`

- [ ] **Step 1: Add journey AC template**

Create `docs/testing/journeys/_template.md` with:

```md
# Journey: <JOURNEY_ID>

## Business Outcome

<One sentence describing user value.>

## Acceptance Criteria

### Scenario 1: <name>

- Given <starting context>
- When <user action>
- Then <observable outcome>

### Scenario 2: <name>

- Given <starting context>
- When <user action>
- Then <observable outcome>

## Out Of Scope

- <explicit non-goal>

## Linked UI Stories

- <issue reference>

## Linked Playwright Specs

- <repo path>
```

- [ ] **Step 2: Add concrete journey docs for first smoke scope**

Create `docs/testing/journeys/JRN-P2-shell-navigation-continuity.md`:

```md
# Journey: JRN-P2-shell-navigation-continuity

## Business Outcome

Users can navigate between primary sections without losing the persistent shell frame.

## Acceptance Criteria

### Scenario 1: Browse to Search keeps shell frame mounted

- Given the user is on `/browse`
- When the user selects `Search` from primary navigation
- Then the header and primary navigation remain visible
- And the main content updates to the Search page title

### Scenario 2: Shell route context updates with navigation

- Given the user is on `/browse`
- When the user selects a different primary route
- Then shell route context reflects the selected route

## Out Of Scope

- Search results behavior
- API-backed data loading

## Linked UI Stories

- #164

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
```

Create `docs/testing/journeys/JRN-P2-not-found-recovery.md`:

```md
# Journey: JRN-P2-not-found-recovery

## Business Outcome

Users can recover from an unknown URL without losing orientation or global navigation.

## Acceptance Criteria

### Scenario 1: Unknown path shows recoverable not-found state

- Given the user opens an unknown route
- When the page renders
- Then a not-found title is shown in content
- And primary navigation remains visible

### Scenario 2: Recovery to Browse from not-found page

- Given the user is on a not-found page
- When the user selects `Browse` in primary navigation
- Then the app navigates to `/browse`
- And Browse page content is visible

## Out Of Scope

- Customized 404 branding
- Logging/telemetry for invalid URLs

## Linked UI Stories

- #164

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
```

Create `docs/testing/journeys/JRN-P3-search-route-deep-link.md`:

```md
# Journey: JRN-P3-search-route-deep-link

## Business Outcome

Users can open the Search route directly from a URL and land in the correct shell and navigation state.

## Acceptance Criteria

### Scenario 1: Direct deep link to `/search`

- Given the user opens `/search` directly
- When the app loads
- Then Search page content is shown
- And Search is marked as the active primary route

### Scenario 2: Deep link with query state

- Given the user opens `/search?query=lake`
- When the app loads
- Then the URL query is preserved
- And shell route context remains Search

## Out Of Scope

- Search API responses
- Search filter semantics

## Linked UI Stories

- #165

## Linked Playwright Specs

- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
- `apps/ui/tests/e2e/technical/navigation-state.spec.ts`
```

- [ ] **Step 3: Add journey traceability mapping**

Create `docs/testing/journey-traceability.md` with:

```md
# Journey Traceability

This document maps business journey IDs to acceptance-criteria docs and executable Playwright coverage.

| Journey ID | Journey Doc | Playwright Specs | Story/Issue |
| --- | --- | --- | --- |
| `JRN-P2-shell-navigation-continuity` | `docs/testing/journeys/JRN-P2-shell-navigation-continuity.md` | `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts` | `#164` |
| `JRN-P2-not-found-recovery` | `docs/testing/journeys/JRN-P2-not-found-recovery.md` | `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts` | `#164` |
| `JRN-P3-search-route-deep-link` | `docs/testing/journeys/JRN-P3-search-route-deep-link.md` | `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`, `apps/ui/tests/e2e/technical/navigation-state.spec.ts` | `#165` |
```

- [ ] **Step 4: Verify traceability IDs are present in tests and docs**

Run:

```bash
rg -n "JRN-P2-shell-navigation-continuity|JRN-P2-not-found-recovery|JRN-P3-search-route-deep-link" apps/ui/tests/e2e docs/testing -S
```

Expected: each journey ID appears in both a journey doc and at least one Playwright spec title.

- [ ] **Step 5: Commit Task 3**

```bash
git add docs/testing/journeys/_template.md docs/testing/journeys/JRN-P2-shell-navigation-continuity.md docs/testing/journeys/JRN-P2-not-found-recovery.md docs/testing/journeys/JRN-P3-search-route-deep-link.md docs/testing/journey-traceability.md
git commit -m "docs(testing): add journey acceptance docs and traceability mapping"
```

### Task 4: Add CI Workflow For Unit, Smoke, And Full Lanes

**Files:**
- Create: `.github/workflows/ui-tests.yml`

- [ ] **Step 1: Add the UI test workflow definition**

Create `.github/workflows/ui-tests.yml` with:

```yaml
name: ui-tests

on:
  pull_request:
    paths:
      - "apps/ui/**"
      - "docs/testing/**"
      - ".github/workflows/ui-tests.yml"
      - ".gitignore"
      - "CONTRIBUTING.md"
  push:
    branches:
      - main
    paths:
      - "apps/ui/**"
      - "docs/testing/**"
      - ".github/workflows/ui-tests.yml"
      - ".gitignore"
      - "CONTRIBUTING.md"
  schedule:
    - cron: "0 5 * * *"
  workflow_dispatch:

jobs:
  ui-unit:
    if: github.event_name != 'schedule'
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/ui/package-lock.json
      - name: Install UI dependencies
        working-directory: apps/ui
        run: npm ci
      - name: Run Vitest unit suite
        working-directory: apps/ui
        run: npm run test

  ui-e2e-smoke:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/ui/package-lock.json
      - name: Install UI dependencies
        working-directory: apps/ui
        run: npm ci
      - name: Install Playwright Chromium
        working-directory: apps/ui
        run: npx playwright install --with-deps chromium
      - name: Run smoke journeys
        working-directory: apps/ui
        run: npm run test:e2e:smoke
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ui-e2e-smoke-report
          path: apps/ui/playwright-report
          if-no-files-found: ignore

  ui-e2e-full:
    if: github.event_name == 'push' || github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/ui/package-lock.json
      - name: Install UI dependencies
        working-directory: apps/ui
        run: npm ci
      - name: Install Playwright Chromium
        working-directory: apps/ui
        run: npx playwright install --with-deps chromium
      - name: Run full E2E lane
        working-directory: apps/ui
        run: npm run test:e2e:full
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: ui-e2e-full-report
          path: apps/ui/playwright-report
          if-no-files-found: ignore
```

- [ ] **Step 2: Validate workflow YAML parses**

Run:

```bash
cd apps/ui
npm run test
npm run test:e2e:smoke
```

Expected: both commands pass, confirming the workflow commands are valid in CI as written.

- [ ] **Step 3: Commit Task 4**

```bash
git add .github/workflows/ui-tests.yml
git commit -m "ci(ui): add unit, smoke, and full playwright workflow lanes"
```

### Task 5: Document Contributor Workflow And Run Final Verification

**Files:**
- Create: `.github/pull_request_template.md`
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Add PR template journey-ID requirement**

Create `.github/pull_request_template.md` with:

```md
## Summary

Describe what changed and why.

## Journey IDs

List impacted journey IDs from `docs/testing/journeys/`:

- [ ] `JRN-*` IDs not applicable (no UI behavior changes)
- Impacted IDs:
  - `JRN-...`

## Validation

- [ ] `cd apps/ui && npm run test`
- [ ] `cd apps/ui && npm run test:e2e:smoke`
- [ ] `cd apps/ui && npm run test:e2e:technical` (if technical behavior changed)
```

- [ ] **Step 2: Update contributor commands for UI testing**

Add this section near the existing command catalog in `CONTRIBUTING.md`:

```md
### UI Testing Commands

UI testing is split into fast component checks and browser-based Playwright checks.

- `cd apps/ui && npm run test`
  - run Vitest unit/component tests
- `cd apps/ui && npm run test:e2e:smoke`
  - run required PR smoke journeys tagged `@smoke`
- `cd apps/ui && npm run test:e2e:technical`
  - run technical Playwright checks tagged `@technical`
- `cd apps/ui && npm run test:e2e:full`
  - run full Playwright lane excluding quarantined tests

Business acceptance criteria live under `docs/testing/journeys/` and are not executable.
Each Playwright journey test title should include a `JRN-*` ID that maps to `docs/testing/journey-traceability.md`.
```

- [ ] **Step 3: Run end-to-end verification commands**

Run:

```bash
cd apps/ui
npm run test
npm run test:e2e:smoke
npm run test:e2e:technical
npm run test:e2e:full
```

Expected: all commands pass.

- [ ] **Step 4: Check changed files and summarize CI/runtime alignment**

Run:

```bash
git status --short
```

Expected changed files (when executing without intermediate commits):
- `apps/ui/package.json`
- `apps/ui/package-lock.json`
- `apps/ui/playwright.config.ts`
- `apps/ui/tests/e2e/journeys/app-shell-journeys.spec.ts`
- `apps/ui/tests/e2e/technical/navigation-state.spec.ts`
- `apps/ui/tests/e2e/support/navAsserts.ts`
- `docs/testing/journeys/_template.md`
- `docs/testing/journeys/JRN-P2-shell-navigation-continuity.md`
- `docs/testing/journeys/JRN-P2-not-found-recovery.md`
- `docs/testing/journeys/JRN-P3-search-route-deep-link.md`
- `docs/testing/journey-traceability.md`
- `.github/workflows/ui-tests.yml`
- `.github/pull_request_template.md`
- `.gitignore`
- `CONTRIBUTING.md`

- [ ] **Step 5: Commit Task 5**

```bash
git add .github/pull_request_template.md CONTRIBUTING.md
git commit -m "docs(ui): require journey-id traceability in pull requests"
```

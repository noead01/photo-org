# UI Testing Strategy Design

Date: 2026-04-27
Scope: UI testing strategy for the React app, balancing business-readable acceptance criteria with maintainable automated coverage

## Summary

Adopt a layered UI testing strategy centered on Playwright for executable end-to-end behavior, while keeping business-readable acceptance criteria in non-executable journey documents.

This strategy intentionally does **not** introduce Cucumber at this stage. It preserves shared business language through journey docs and traceability, while avoiding the maintenance overhead of executable Gherkin.

## Goals

- keep business acceptance criteria readable and shared across product/QA/engineering
- keep executable UI tests maintainable and fast enough for PR feedback
- enforce clear traceability from journey intent to automated verification
- fit UI CI gating within a 30-minute budget per pull request

## Non-Goals

- no executable Gherkin/Cucumber adoption in this phase
- no replacement of existing Vitest + React Testing Library unit/component coverage
- no broad browser-matrix gating on every PR

## Decision Snapshot

- Testing approach: **Approach C**
  - Playwright-only executable E2E coverage
  - business ACs remain documentation artifacts
- Business AC format: Given/When/Then style, non-executable
- AC-to-test mapping model:
  - Given/When/Then journey docs map to user journeys
  - Playwright tests map to journey IDs and implementation details
- Ownership model: shared product/QA/engineering ownership for journey docs, engineering ownership for test code
- PR CI budget target: under 30 minutes

## Architecture

### Layered Testing Model

1. `Vitest + RTL` covers component behavior, state handling, and UI edge cases quickly.
2. `Playwright journey tests` validate critical user outcomes end-to-end.
3. `Playwright technical tests` validate reliability and platform concerns (URL persistence, error paths, accessibility smoke checks).
4. `Journey docs` define business intent and acceptance criteria in readable language.

### Boundary Rules

- Journey docs state user outcomes and acceptance semantics, not selector-level detail.
- Playwright specs verify the concrete UI behavior implementing those outcomes.
- One journey can map to multiple Playwright tests.
- Every Playwright journey spec must reference at least one `journey_id`.

## Structure And Conventions

### Repository Layout

- `apps/ui/tests/e2e/`
  - root for executable Playwright tests
- `apps/ui/tests/e2e/journeys/`
  - journey outcome tests (happy paths + critical alternates)
- `apps/ui/tests/e2e/technical/`
  - technical behavior tests not primarily business-facing
- `docs/testing/journeys/`
  - journey AC docs in readable Given/When/Then format (non-executable)
- `docs/testing/journey-traceability.md`
  - mapping file: `journey_id -> doc path -> Playwright specs -> issue/story refs`

### Naming And Traceability

- Journey ID format: `JRN-P{phase}-{slug}`
  - example: `JRN-P3-search-with-date-filter`
- Every journey doc starts with:
  - `Journey ID`
  - `Business Outcome`
  - `Acceptance Criteria`
  - `Out Of Scope`
- Every Playwright journey test title/tag includes journey ID(s).
- PRs modifying UI behavior must list affected journey IDs.

## CI Strategy

Target: keep required PR checks under 30 minutes.

### PR Required Jobs

1. `ui-unit`
  - runner: Vitest + RTL
  - target runtime: < 5 minutes

2. `ui-e2e-smoke`
  - runner: Playwright
  - scope: smallest critical subset of journeys
  - target runtime: 8-12 minutes with sharding/parallelism

### Non-Blocking Jobs

3. `ui-e2e-full`
  - runner: Playwright
  - trigger: merge to `main`, nightly, and manual dispatch
  - scope: full journey + technical suites
  - target runtime: 20-30 minutes

### Runtime Controls

- Tag categories: `@smoke`, `@journey`, `@technical`, `@slow`, `@quarantine`
- Required PR lane includes `@smoke` only
- Flaky tests move to `@quarantine` until stabilized
- Cross-browser coverage defaults to full/nightly rather than required PR gates
- Use deterministic seed data and stable environment bootstrapping

## Workflow And Governance

### Ownership

- Product + QA:
  - co-author and review journey AC docs
- Engineering:
  - implement Playwright tests and maintain infrastructure
- Review expectations:
  - journey-doc changes require product/QA reviewer
  - Playwright infra changes require engineering reviewer

### Definition Of Ready (Journey Automation)

- journey doc has stable `Journey ID`
- business outcome and acceptance criteria are explicit
- dependencies and data assumptions are identified
- required states are explicit:
  - success
  - empty/no-match (where applicable)
  - failure behavior

### Definition Of Done (Per Journey)

- journey AC doc approved
- linked Playwright tests added or updated
- traceability mapping updated
- correct tags applied (`@smoke` only if PR-critical)
- required CI lane is green without unresolved flaky behavior

## Migration Plan

1. Scaffold Playwright in `apps/ui` and add CI jobs (`ui-e2e-smoke`, `ui-e2e-full`).
2. Add journey doc template and `journey-traceability.md`.
3. Implement first 3 smoke journeys aligned to currently available Phase 2/3 UI surfaces.
4. Add baseline technical suite coverage (URL state persistence, major error state, accessibility smoke).
5. Expand journey catalog phase-by-phase as stories ship.

## Risks And Mitigations

- Risk: AC docs drift from executable behavior.
  - Mitigation: require journey ID references in Playwright tests and PR descriptions.
- Risk: smoke suite grows beyond PR budget.
  - Mitigation: strict `@smoke` admission gate and periodic suite pruning.
- Risk: flaky E2E tests undermine trust.
  - Mitigation: quarantine policy plus deterministic data/environment controls.

## Open Questions

- None for this decision slice. Execution details belong in the implementation plan.

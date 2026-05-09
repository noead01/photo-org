# UI Remediation Workstream Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement one linked plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Distribute the UI SRP and standard-component remediation work into independent, developer-owned workstreams.

**Architecture:** Each workstream narrows one responsibility boundary in `apps/ui`. Shared primitives and API/domain modules are prioritized before page-level cleanup so later refactors can reuse them.

**Tech Stack:** React 18, React Router 6, Vite, TypeScript, Vitest, Testing Library, `react-paginate`, candidate additions `nuqs` and `@radix-ui/react-slider`.

---

## Recommended Assignment Order

1. [Standardize pagination](./2026-05-09-ui-pagination-standardization.md)
2. [Standardize confidence sliders](./2026-05-09-ui-confidence-slider-standardization.md)
3. [Standardize URL and storage-backed state](./2026-05-09-ui-query-persistence-standardization.md)
4. [Extract shared face labeling domain/API modules](./2026-05-09-ui-face-labeling-shared-domain.md)
5. [Split Library route responsibilities](./2026-05-09-ui-library-route-srp.md)
6. [Split Photo Detail route responsibilities](./2026-05-09-ui-photo-detail-srp.md)
7. [Split Albums route responsibilities](./2026-05-09-ui-albums-route-srp.md)
8. [Split People Management route responsibilities](./2026-05-09-ui-people-management-srp.md)

## Ownership Notes

- Pagination, slider, and query-state standardization can run independently if developers coordinate package changes in `apps/ui/package.json`.
- Face labeling shared domain work should land before Photo Detail and Library face-panel cleanups, because those pages duplicate face assignment behavior.
- Library route SRP cleanup is the largest workstream. Assign it to one developer after pagination/query-state primitives are available.
- Albums and People Management cleanup can run independently of Library if they avoid changing shared album API signatures at the same time.

## Verification Baseline

- Run UI unit tests after each workstream: `npm --prefix apps/ui test`.
- Run type/build verification before merging any package dependency change: `npm --prefix apps/ui run build`.
- Run focused tests listed in each plan before the full suite.


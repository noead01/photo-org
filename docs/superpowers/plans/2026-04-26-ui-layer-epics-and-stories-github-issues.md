# UI Layer EPIC And Story GitHub Issues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the approved UI-layer EPICs and child stories in GitHub for Phases 2-6, with labels, parent/child links, and backend dependency links so the backlog is ready for refinement.

**Architecture:** Use the existing GitHub issue hierarchy style already used in this repository: one issue as UI EPIC per phase and child implementation issues linked in each EPIC checklist. Keep the UI EPICs phase-aligned and fold app-shell/layout foundations into the Phase 2 UI EPIC. Apply existing `phase:*`, `priority:*`, `type:*`, and `area:web` labels consistently.

**Tech Stack:** GitHub connector tools (`_create_issue`, `_update_issue`, `_add_issue_labels`, `_fetch_issue`, `_search_issues`), Markdown issue templates, existing roadmap/phase issue taxonomy.

---

## File Structure And Ownership

- Modify: `docs/superpowers/plans/2026-04-26-ui-layer-epics-and-stories-github-issues.md` (task tracking updates only)
- Read: `docs/superpowers/specs/2026-04-26-ui-layer-epics-and-stories-design.md` (approved source of truth)
- External writes: GitHub issues in `noead01/photo-org`

No application code or tests are modified in this plan.

### Task 1: Validate Prerequisites And Avoid Duplicates

**Files:**
- Read: `docs/superpowers/specs/2026-04-26-ui-layer-epics-and-stories-design.md`
- External read: existing GitHub issues in `noead01/photo-org`

- [ ] **Step 1: Confirm backend phase parent issue anchors exist**

Run searches for:
- `Phase 2: Browse And Inspect`
- `Phase 3: Search And Filtering`
- `Phase 4: Face Labeling Workflow`
- `Phase 5: Recognition Suggestions`
- `Phase 6: Operational Admin Features`

Expected: issues `#9`, `#10`, `#11`, `#12`, `#13` are present.

- [ ] **Step 2: Confirm no existing UI EPIC duplicates**

Search GitHub issues for:
- `"UI EPIC: Phase 2 Browse And Inspect"`
- `"UI EPIC: Phase 3 Search And Filtering"`
- `"UI EPIC: Phase 4 Face Labeling Workflow"`
- `"UI EPIC: Phase 5 Recognition Suggestions"`
- `"UI EPIC: Phase 6 Operational Admin Features"`

Expected: no existing matching issues.

- [ ] **Step 3: Confirm labeling taxonomy target**

Use existing issue patterns to confirm intended labels:
- EPIC: `phase:*`, `priority:p1` or `priority:p2`, `type:parent`, `area:web`
- Story: `phase:*`, phase-matching priority, `type:implementation`, `area:web`

Expected: no new label names required.

### Task 2: Create The 5 UI EPIC Issues

**Files:**
- Source: `docs/superpowers/specs/2026-04-26-ui-layer-epics-and-stories-design.md`
- External write: 5 new GitHub issues

- [ ] **Step 1: Create UI EPIC for Phase 2**

Create issue title:
`UI EPIC: Phase 2 Browse And Inspect`

Body sections:
- Goal
- Demo Capabilities (global app shell + browse/detail)
- Out Of Scope
- Child Stories (initially empty list; populated with concrete links in Task 8)
- Completion Criteria
- Dependencies: backend parent `#9`

- [ ] **Step 2: Create UI EPIC for Phase 3**

Create issue title:
`UI EPIC: Phase 3 Search And Filtering`

Dependencies include backend parent `#10`.

- [ ] **Step 3: Create UI EPIC for Phase 4**

Create issue title:
`UI EPIC: Phase 4 Face Labeling Workflow`

Dependencies include backend parent `#11`.

- [ ] **Step 4: Create UI EPIC for Phase 5**

Create issue title:
`UI EPIC: Phase 5 Recognition Suggestions`

Dependencies include backend parent `#12`.

- [ ] **Step 5: Create UI EPIC for Phase 6**

Create issue title:
`UI EPIC: Phase 6 Operational Admin Features`

Dependencies include backend parent `#13`.

- [ ] **Step 6: Verify all 5 EPIC issues created**

Fetch each issue and verify title/body presence.

Expected: 5 new issue numbers captured for later checklist linking.

### Task 3: Create Phase 2 UI Story Issues (10)

**Files:**
- Source: `docs/superpowers/specs/2026-04-26-ui-layer-epics-and-stories-design.md`
- External write: 10 new GitHub issues

- [ ] **Step 1: Create story issue `Implement app shell frame with global header/nav/content regions`**
- [ ] **Step 2: Create story issue `Implement logged-in user menu and account action entry points`**
- [ ] **Step 3: Create story issue `Implement global navigation state model for active routes and page context`**
- [ ] **Step 4: Create story issue `Implement responsive app layout behavior for desktop/tablet/mobile`**
- [ ] **Step 5: Create story issue `Implement global loading/error/notification surface patterns`**
- [ ] **Step 6: Create story issue `Implement photo gallery grid with deterministic ordering and pagination controls`**
- [ ] **Step 7: Create story issue `Implement photo detail view with metadata presentation`**
- [ ] **Step 8: Create story issue `Implement face-region overlays in photo detail`**
- [ ] **Step 9: Create story issue `Implement ingest-status visibility in gallery and detail contexts`**
- [ ] **Step 10: Create story issue `Implement browse/detail empty-loading-error states with keyboard focus behavior`**

Each issue must include:
- Summary
- Why This Matters
- Scope
- Non-Goals
- Acceptance Criteria
- Verification
- Dependencies: parent UI EPIC issue + backend dependency `#9` and relevant child backend issues (`#30`-`#33`) as applicable

### Task 4: Create Phase 3 UI Story Issues (8)

**Files:**
- External write: 8 new GitHub issues

- [ ] **Step 1: Create `Implement tokenized search bar interactions for query submit/reset`**
- [ ] **Step 2: Create `Implement date-range filter UI with inclusive boundary semantics`**
- [ ] **Step 3: Create `Implement person filter picker with fuzzy-name matching behavior`**
- [ ] **Step 4: Create `Implement location-radius filter input UX with lat-lon-radius validation`**
- [ ] **Step 5: Create `Implement facet panel for has-faces and path-hint filters with counts`**
- [ ] **Step 6: Create `Implement URL-synced filter state with deep-link restoration`**
- [ ] **Step 7: Create `Implement stable sort and deterministic pagination behavior for filtered results`**
- [ ] **Step 8: Create `Implement search result empty-no-match-error messaging patterns`**

Dependencies: Phase 3 backend parent `#10` and relevant backend stories `#34`-`#40`.

### Task 5: Create Phase 4 UI Story Issues (8)

**Files:**
- External write: 8 new GitHub issues

- [ ] **Step 1: Create `Implement people management screen for create-list-rename-delete workflows`**
- [ ] **Step 2: Create `Implement face-to-person assignment interactions in photo detail context`**
- [ ] **Step 3: Create `Implement face-label correction and reassignment workflow UI`**
- [ ] **Step 4: Create `Implement label provenance indicators and detail affordances`**
- [ ] **Step 5: Create `Implement permission-aware action gating with read-only fallbacks`**
- [ ] **Step 6: Create `Implement multi-item labeling navigation flow`**
- [ ] **Step 7: Create `Implement assignment and correction success/failure feedback patterns`**
- [ ] **Step 8: Create `Implement conflict and blocked-action UX for 409/permission-denied responses`**

Dependencies: Phase 4 backend parent `#11` and relevant backend stories `#41`, `#42`, `#43`, `#44`, `#45`, `#46`, `#133`.

### Task 6: Create Phase 5 UI Story Issues (8)

**Files:**
- External write: 8 new GitHub issues

- [ ] **Step 1: Create `Implement review-needed suggestion queue screen`**
- [ ] **Step 2: Create `Implement candidate comparison card UI with confidence-band communication`**
- [ ] **Step 3: Create `Implement accept-suggestion action flow with deterministic state updates`**
- [ ] **Step 4: Create `Implement reject-suggestion action flow with explicit unresolved-state behavior`**
- [ ] **Step 5: Create `Implement correct-to-different-person flow from suggestion context`**
- [ ] **Step 6: Create `Implement provenance and model-version details panel for suggestion transparency`**
- [ ] **Step 7: Create `Implement throughput aids for suggestion review navigation`**
- [ ] **Step 8: Create `Implement suggestion queue empty-loading-error states with operator guidance`**

Dependencies: Phase 5 backend parent `#12` and relevant backend stories `#47`, `#48`, `#49`, `#50`, `#51`, `#52`.

### Task 7: Create Phase 6 UI Story Issues (8)

**Files:**
- External write: 8 new GitHub issues

- [ ] **Step 1: Create `Implement storage-source health dashboard table UI`**
- [ ] **Step 2: Create `Implement ingest-failure timeline with inspectable error details`**
- [ ] **Step 3: Create `Implement source enable-disable controls with confirmation and outcome feedback`**
- [ ] **Step 4: Create `Implement manual rescan-backfill trigger UI with status tracking`**
- [ ] **Step 5: Create `Implement catalog metrics cards for size-face-unlabeled-pending workloads`**
- [ ] **Step 6: Create `Implement operational filtering and sorting controls for source/failure views`**
- [ ] **Step 7: Create `Implement admin dashboard empty-loading-error-degraded state messaging`**
- [ ] **Step 8: Create `Implement permission-aware admin action gating with non-destructive defaults`**

Dependencies: Phase 6 backend parent `#13` and relevant backend stories `#53`, `#54`, `#55`, `#56`, `#57`, `#121`, `#122`.

### Task 8: Backfill UI EPIC Child Story Checklists

**Files:**
- External update: 5 UI EPIC issues

- [ ] **Step 1: Update Phase 2 UI EPIC child checklist with the 10 created Phase 2 story issue links**
- [ ] **Step 2: Update Phase 3 UI EPIC child checklist with the 8 created Phase 3 story issue links**
- [ ] **Step 3: Update Phase 4 UI EPIC child checklist with the 8 created Phase 4 story issue links**
- [ ] **Step 4: Update Phase 5 UI EPIC child checklist with the 8 created Phase 5 story issue links**
- [ ] **Step 5: Update Phase 6 UI EPIC child checklist with the 8 created Phase 6 story issue links**

Expected: each UI EPIC presents a complete, linked child-story checklist.

### Task 9: Apply Labels To EPICs And Stories

**Files:**
- External update: all created GitHub issues

- [ ] **Step 1: Label UI EPIC issues**

Apply:
- Phase 2 UI EPIC: `phase:2`, `priority:p1`, `type:parent`, `area:web`
- Phase 3 UI EPIC: `phase:3`, `priority:p1`, `type:parent`, `area:web`
- Phase 4 UI EPIC: `phase:4`, `priority:p1`, `type:parent`, `area:web`
- Phase 5 UI EPIC: `phase:5`, `priority:p2`, `type:parent`, `area:web`
- Phase 6 UI EPIC: `phase:6`, `priority:p2`, `type:parent`, `area:web`

- [ ] **Step 2: Label child stories**

Apply for each story:
- `phase:*` matching its EPIC
- phase-matching priority (`p1` for phases 2-4, `p2` for phases 5-6)
- `type:implementation`
- `area:web`

- [ ] **Step 3: Verify label application**

Fetch one EPIC and one story per phase to confirm expected labels exist.

### Task 10: Cross-Link Backend Parent Issues

**Files:**
- External update: backend phase parent issues `#9`, `#10`, `#11`, `#12`, `#13`

- [ ] **Step 1: Add a top-level comment to #9 linking the new Phase 2 UI EPIC**
- [ ] **Step 2: Add a top-level comment to #10 linking the new Phase 3 UI EPIC**
- [ ] **Step 3: Add a top-level comment to #11 linking the new Phase 4 UI EPIC**
- [ ] **Step 4: Add a top-level comment to #12 linking the new Phase 5 UI EPIC**
- [ ] **Step 5: Add a top-level comment to #13 linking the new Phase 6 UI EPIC**

Each comment should state the UI EPIC is the frontend implementation track aligned to that backend phase.

### Task 11: Final Verification

**Files:**
- External read: created/updated GitHub issues

- [ ] **Step 1: Verify issue counts**

Expected new issues:
- 5 UI EPIC issues
- 42 UI story issues
- Total new issues: 47

- [ ] **Step 2: Verify every story references exactly one UI EPIC parent and at least one backend dependency**

Sample-check all stories by phase.

- [ ] **Step 3: Verify each UI EPIC has complete linked child checklist and dependency section**

Expected: all child links and dependency links are fully populated.

- [ ] **Step 4: Capture created issue numbers and summarize by phase**

Prepare final report:
- UI EPIC numbers by phase
- child issue ranges/counts by phase
- any follow-up refinement suggestions

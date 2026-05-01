# Issue 185 Label Provenance Indicators And Detail Affordances Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add provenance badges and inline provenance details for face labels in photo detail, including compact overlay badges and explicit legacy fallback handling.

**Architecture:** Extend photo-detail face payloads with latest matching face-label provenance metadata, then thread those fields through `PhotoDetailRoutePage` into `FaceAssignmentControls`. Render compact emoji badges in labeled-face rows and overlay regions, and use a single-expanded inline panel for provenance details.

**Tech Stack:** FastAPI + SQLAlchemy, React + TypeScript, Vitest, Pytest.

---

### Task 1: Backend Photo Detail Provenance Fields

**Files:**
- Modify: `apps/api/app/repositories/photos_repo.py`
- Modify: `apps/api/app/schemas/photo_response.py`
- Test: `apps/api/tests/test_photo_detail_api.py`

- [ ] **Step 1: Add failing API tests for provenance fields**
- [ ] **Step 2: Run targeted pytest to confirm failure**
Run: `uv run pytest apps/api/tests/test_photo_detail_api.py -k provenance -q`
- [ ] **Step 3: Implement repository provenance lookup and schema fields**
- [ ] **Step 4: Re-run targeted pytest and full photo detail API test file**
Run: `uv run pytest apps/api/tests/test_photo_detail_api.py -q`
- [ ] **Step 5: Commit backend changes**

### Task 2: Face Assignment Controls Provenance UI

**Files:**
- Modify: `apps/ui/src/pages/FaceAssignmentControls.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- Test: `apps/ui/src/pages/FaceAssignmentControls.test.tsx`

- [ ] **Step 1: Add failing UI tests for provenance badges and inline panel**
- [ ] **Step 2: Run targeted Vitest to confirm failure**
Run: `npm --prefix apps/ui test -- src/pages/FaceAssignmentControls.test.tsx`
- [ ] **Step 3: Implement badge mapping, expandable details, and fallback rendering**
- [ ] **Step 4: Add CSS for compact badges and details layout**
- [ ] **Step 5: Re-run targeted Vitest**
Run: `npm --prefix apps/ui test -- src/pages/FaceAssignmentControls.test.tsx`
- [ ] **Step 6: Commit UI control changes**

### Task 3: Overlay Badge Integration In Photo Detail

**Files:**
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Test: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`

- [ ] **Step 1: Add failing integration tests for overlay provenance badge interaction**
- [ ] **Step 2: Run targeted Vitest to confirm failure**
Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx`
- [ ] **Step 3: Implement overlay badges and link click to inline provenance panel expansion**
- [ ] **Step 4: Re-run targeted Vitest**
Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx`
- [ ] **Step 5: Commit integration changes**

### Task 4: Final Verification

**Files:**
- No additional files expected

- [ ] **Step 1: Run API + UI targeted regression commands**
Run: `uv run pytest apps/api/tests/test_photo_detail_api.py -q`
Run: `npm --prefix apps/ui test -- src/pages/FaceAssignmentControls.test.tsx src/pages/PhotoDetailRoutePage.test.tsx`
- [ ] **Step 2: Review `git status` and summarize completed behavior**
- [ ] **Step 3: Final commit if any remaining staged verification-only updates exist**

# Developer Workflow And Environment Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document one clear Phase 0 contributor workflow and lock its environment contracts into the repo with lightweight verification.

**Architecture:** Keep `CONTRIBUTING.md` as the single contributor-facing source of truth for the baseline setup and verification path. Update existing documentation to avoid duplicate contributor guidance, and extend documentation tests so the expected commands, boundaries, and environment assumptions stay explicit.

**Tech Stack:** Markdown documentation, Python/pytest doc assertions, root `Makefile`, repo CLI wrapper script

---

### Task 1: Define The Baseline Contributor Workflow In Docs

**Files:**
- Modify: `CONTRIBUTING.md`
- Reference: `README.md`
- Reference: `Makefile`
- Reference: `scripts/photo-org`

- [ ] **Step 1: Write the failing documentation assertions**

```python
def test_contributing_documents_baseline_phase_zero_workflow():
    contributing = (_repo_root() / "CONTRIBUTING.md").read_text()

    assert "Baseline Phase 0 Workflow" in contributing
    assert "1. `make sync`" in contributing
    assert "2. `make migrate`" in contributing
    assert "3. `make seed-corpus-check`" in contributing
    assert "4. `make seed-corpus-load`" in contributing
    assert "5. `make check`" in contributing
```

- [ ] **Step 2: Run the targeted doc test to verify it fails**

Run: `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: FAIL because `CONTRIBUTING.md` does not yet define one ordered Phase 0 workflow section.

- [ ] **Step 3: Update `CONTRIBUTING.md` with one ordered baseline path**

Document:

```md
## Baseline Phase 0 Workflow

1. `make sync`
2. `make migrate` when a local database is needed
3. `make seed-corpus-check`
4. `make seed-corpus-load`
5. `make check`
6. `make test-all` and `make test-e2e` before broader changes or handoff
```

Also clarify:

- the repo assumes local Python development through `uv`
- generated local state belongs under `.local/`
- the current supported workflow is backend/API focused
- local stack startup through Compose is not yet the supported baseline contributor path

- [ ] **Step 4: Run the targeted doc test to verify it passes**

Run: `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md apps/api/tests/test_seed_corpus_manifest.py
git commit -m "docs(dev): define baseline phase zero workflow"
```

### Task 2: Keep README User-Facing And Link Contributor Workflow Clearly

**Files:**
- Modify: `README.md`
- Reference: `CONTRIBUTING.md`

- [ ] **Step 1: Write the failing documentation assertion**

```python
def test_readme_points_contributors_to_contributing_for_local_workflow():
    readme = (_repo_root() / "README.md").read_text()

    assert "For contributor setup and validation commands, see [CONTRIBUTING.md]" in readme
```

- [ ] **Step 2: Run the targeted doc test to verify it fails**

Run: `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: FAIL because `README.md` does not yet point contributors to the documented baseline workflow in the required wording.

- [ ] **Step 3: Add the contributor-workflow handoff to `README.md`**

Add or tighten README wording so:

- contributor setup is explicitly delegated to `CONTRIBUTING.md`
- user/evaluator setup language stays high level
- the README does not become a second source of truth for contributor commands

- [ ] **Step 4: Run the targeted doc test to verify it passes**

Run: `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md apps/api/tests/test_seed_corpus_manifest.py
git commit -m "docs(readme): point contributors to workflow source"
```

### Task 3: Lock Environment Contracts And Verification Boundaries

**Files:**
- Modify: `apps/api/tests/test_seed_corpus_manifest.py`
- Modify: `CONTRIBUTING.md`
- Reference: `docs/ITERATIVE_DEVELOPMENT.md`

- [ ] **Step 1: Write the failing assertions for environment contracts**

```python
def test_contributing_documents_environment_contracts():
    contributing = (_repo_root() / "CONTRIBUTING.md").read_text()

    assert "The repo assumes local Python development through `uv`." in contributing
    assert "Generated local artifacts should go under `.local/`." in contributing
    assert "Compose-based stack startup is not yet the supported baseline contributor workflow." in contributing
```

- [ ] **Step 2: Run the targeted doc test to verify it fails**

Run: `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
Expected: FAIL because at least one required contract statement is missing or too implicit.

- [ ] **Step 3: Implement the minimal doc and test updates**

Extend `apps/api/tests/test_seed_corpus_manifest.py` with explicit assertions for:

- the ordered baseline workflow commands
- `.local/` generated artifact guidance
- `uv` as the local Python environment tool
- contributor workflow ownership in `CONTRIBUTING.md`
- the boundary that Compose startup is not yet the supported baseline path

Update `CONTRIBUTING.md` only as needed to satisfy those exact contracts without adding release-process scope.

- [ ] **Step 4: Run the documentation-focused test and baseline repo checks**

Run:

- `PYTHONPATH=apps/api .venv/bin/python -m pytest apps/api/tests/test_seed_corpus_manifest.py -q`
- `make check`

Expected:

- PASS for the documentation assertions
- PASS for the focused lint and API pytest slice

- [ ] **Step 5: Commit**

```bash
git add CONTRIBUTING.md README.md apps/api/tests/test_seed_corpus_manifest.py
git commit -m "test(docs): lock developer workflow contracts"
```


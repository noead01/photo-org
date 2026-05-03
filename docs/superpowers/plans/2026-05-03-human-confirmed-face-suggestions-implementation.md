# Human-Confirmed Face Suggestions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a human-confirmed-only face assignment workflow with proactive, debounced heuristic suggestion recomputation and certainty-aware Library person filtering.

**Architecture:** Keep `faces.person_id` writable only by human-review endpoints; replace machine auto-apply behavior with persisted suggestion snapshots derived from human-confirmed exemplars. Add person representation aggregates and a recompute pipeline that runs in the worker path, then expose certainty mode in backend search filters and Library UI controls.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pgvector/JSON embeddings, Pytest, React, TypeScript, Vitest.

---

## Scope Check

This feature spans tightly-coupled backend schema, recognition services, queue processing, API contracts, and Library UI filters. It should stay in one plan so all contract changes land atomically and test coverage stays coherent.

## File Structure

- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
  - Remove `machine_applied` label source and add new tables for suggestion workflow state.
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
  - Export new tables/constants and remove deprecated source constant.
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
  - Apply schema updates directly in initial migration.
- Create: `apps/api/app/services/person_representations.py`
  - Compute/update per-person centroid/count/dispersion from `human_confirmed` exemplars.
- Create: `apps/api/app/services/face_suggestions.py`
  - Score/persist ranked suggestions for unlabeled faces.
- Modify: `apps/api/app/services/recognition_policy.py`
  - Remove `auto_apply` decision band and keep heuristic visibility policy only.
- Modify: `apps/api/app/services/face_candidates.py`
  - Read from persisted suggestions and stop auto-apply semantics.
- Modify: `apps/api/app/services/face_assignment.py`
  - Enqueue debounced recompute requests on human-confirmed mutations.
- Modify: `apps/api/app/services/ingest_queue_processor.py`
  - Process recompute queue payloads and refresh suggestion snapshots.
- Modify: `apps/api/app/routers/face_assignments.py`
  - Remove `auto_applied_assignment` from response contract and execution path.
- Modify: `apps/api/app/schemas/search_request.py`
  - Add certainty-mode filter fields.
- Modify: `apps/api/app/repositories/photos_repo.py`
  - Apply certainty-aware people filtering and facet counts.
- Modify: `apps/api/app/domain/facets.py`
  - Add certainty-aware people facet support.
- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
  - Keep suggestions clickable, remove auto-apply handling branch.
- Modify: `apps/ui/src/pages/library/libraryRouteTypes.ts`
  - Extend URL/filter state for certainty mode + threshold.
- Modify: `apps/ui/src/pages/library/libraryRouteSearchState.ts`
  - Parse/serialize certainty mode and threshold into request filters.
- Modify: `apps/ui/src/pages/library/libraryRouteApi.ts`
  - Send certainty fields to search API.
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
  - Add certainty controls in Person filter surface.
- Modify: `apps/ui/src/pages/search/facetFilters.ts`
  - Parse certainty-aware facet payloads.
- Modify: `apps/ui/src/pages/search/FacetFilterPanel.tsx`
  - Show certainty-aware people facet counts.
- Modify: `apps/ui/src/pages/FaceAssignmentControls.tsx`
  - Remove `machine_applied` source branch from badge text.
- Modify: `apps/ui/src/pages/FaceBBoxOverlay.tsx`
  - Remove `machine_applied` from `FaceLabelSource` union.
- Test: `apps/api/tests/test_migrations.py`
- Test: `apps/api/tests/test_recognition_policy.py`
- Test: `apps/api/tests/test_face_candidates_service.py`
- Test: `apps/api/tests/test_face_candidates_api.py`
- Test: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_queue_store.py`
- Create Test: `apps/api/tests/test_person_representations_service.py`
- Create Test: `apps/api/tests/test_face_suggestions_service.py`
- Modify Test: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`
- Modify Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`
- Create/Modify Test: `apps/ui/src/pages/library/libraryRouteSearchState.test.ts`

### Task 1: Schema Baseline for Human-Confirmed-Only Labels and Suggestion Tables

**Files:**
- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Modify: `packages/db-schema/photoorg_db_schema/__init__.py`
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
- Test: `apps/api/tests/test_migrations.py`

- [ ] **Step 1: Write failing migration tests for new/updated tables and constraints**

```python
def test_upgrade_database_face_label_sources_exclude_machine_applied(tmp_path):
    from app.migrations import upgrade_database
    database_url = f"sqlite:///{tmp_path / 'label-source-no-machine-applied.db'}"
    upgrade_database(database_url)
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                insert(face_labels).values(
                    face_label_id="bad-source",
                    face_id="face-1",
                    person_id="person-1",
                    label_source="machine_applied",
                )
            )

def test_upgrade_database_creates_person_representations_and_face_suggestions(tmp_path):
    from app.migrations import upgrade_database
    database_url = f"sqlite:///{tmp_path / 'suggestion-tables.db'}"
    upgrade_database(database_url)
    assert {"person_representations", "face_suggestions"} <= set(inspector.get_table_names())
```

- [ ] **Step 2: Run migration tests to verify failure**

Run: `uv run pytest apps/api/tests/test_migrations.py -k "machine_applied or face_suggestions or person_representations" -q`  
Expected: FAIL with missing tables/constraint mismatch.

- [ ] **Step 3: Implement schema and initial migration updates**

```python
# packages/db-schema/photoorg_db_schema/schema.py
FACE_LABEL_SOURCE_HUMAN_CONFIRMED = "human_confirmed"
FACE_LABEL_SOURCE_MACHINE_SUGGESTED = "machine_suggested"

face_labels = Table(
    "face_labels",
    metadata,
    Column("face_label_id", String(36), primary_key=True),
    Column("face_id", String(36), ForeignKey("faces.face_id", ondelete="CASCADE"), nullable=False),
    Column("person_id", String(36), ForeignKey("people.person_id", ondelete="CASCADE"), nullable=False),
    Column("label_source", String, nullable=False),
    CheckConstraint(
        "label_source IN ('human_confirmed', 'machine_suggested')",
        name="ck_face_labels_label_source",
    ),
)

person_representations = Table(
    "person_representations",
    metadata,
    Column("person_id", String(36), ForeignKey("people.person_id", ondelete="CASCADE"), primary_key=True),
    Column("centroid_embedding", JSON()),
    Column("confirmed_face_count", Integer, nullable=False, server_default=text("0")),
    Column("dispersion_score", Float),
    Column("representation_version", Integer, nullable=False, server_default=text("1")),
    Column("computed_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("model_version", String, nullable=False, server_default=text("'nearest-neighbor-cosine-v1'")),
    Column("provenance", JSON()),
)
```

- [ ] **Step 4: Re-run migration tests**

Run: `uv run pytest apps/api/tests/test_migrations.py -k "machine_applied or face_suggestions or person_representations" -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/db-schema/photoorg_db_schema/schema.py \
  packages/db-schema/photoorg_db_schema/__init__.py \
  apps/api/alembic/versions/20260321_000001_initial_schema.py \
  apps/api/tests/test_migrations.py
git commit -m "db: remove machine_applied source and add suggestion state tables"
```

### Task 2: Recognition Policy and Candidate API Contract Without Auto-Apply

**Files:**
- Modify: `apps/api/app/services/recognition_policy.py`
- Modify: `apps/api/app/services/face_candidates.py`
- Modify: `apps/api/app/routers/face_assignments.py`
- Test: `apps/api/tests/test_recognition_policy.py`
- Test: `apps/api/tests/test_face_candidates_service.py`
- Test: `apps/api/tests/test_face_candidates_api.py`

- [ ] **Step 1: Write failing tests that remove auto-apply semantics**

```python
def test_classify_suggestion_confidence_has_no_auto_apply_band():
    assert classify_suggestion_confidence(0.95, review_threshold=0.7) == "review_needed"

def test_face_candidates_api_never_returns_auto_applied_assignment(tmp_path, monkeypatch):
    payload = response.json()
    assert "auto_applied_assignment" not in payload
    assert payload["suggestion_policy"]["decision"] in {"review_needed", "no_suggestion"}
```

- [ ] **Step 2: Run targeted candidate/policy tests and confirm failure**

Run: `uv run pytest apps/api/tests/test_recognition_policy.py apps/api/tests/test_face_candidates_service.py apps/api/tests/test_face_candidates_api.py -q`  
Expected: FAIL on `auto_apply` expectations.

- [ ] **Step 3: Implement policy and router changes**

```python
# recognition_policy.py
SUGGESTION_DECISION_REVIEW_NEEDED = "review_needed"
SUGGESTION_DECISION_NO_SUGGESTION = "no_suggestion"

def classify_suggestion_confidence(confidence: float, *, review_threshold: float) -> str:
    bounded_confidence = min(1.0, max(0.0, confidence))
    if bounded_confidence >= review_threshold:
        return SUGGESTION_DECISION_REVIEW_NEEDED
    return SUGGESTION_DECISION_NO_SUGGESTION
```

```python
# face_assignments.py response model
class FaceSuggestionPolicyResponse(BaseModel):
    decision: Literal["review_needed", "no_suggestion"]
```

- [ ] **Step 4: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_recognition_policy.py apps/api/tests/test_face_candidates_service.py apps/api/tests/test_face_candidates_api.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/recognition_policy.py \
  apps/api/app/services/face_candidates.py \
  apps/api/app/routers/face_assignments.py \
  apps/api/tests/test_recognition_policy.py \
  apps/api/tests/test_face_candidates_service.py \
  apps/api/tests/test_face_candidates_api.py
git commit -m "api: remove machine auto-apply from recognition candidate workflow"
```

### Task 3: Person Representation Aggregate Service

**Files:**
- Create: `apps/api/app/services/person_representations.py`
- Test: `apps/api/tests/test_person_representations_service.py`

- [ ] **Step 1: Write failing tests for centroid/count/dispersion recompute**

```python
def test_refresh_person_representation_uses_human_confirmed_faces_only(tmp_path):
    refresh_person_representation(connection, person_id="person-1")
    row = connection.execute(
        select(person_representations).where(person_representations.c.person_id == "person-1")
    ).mappings().one()
    assert row["confirmed_face_count"] == 3
    assert row["centroid_embedding"] == pytest.approx([0.6, 0.4], abs=1e-6)
```

- [ ] **Step 2: Run targeted representation tests**

Run: `uv run pytest apps/api/tests/test_person_representations_service.py -q`  
Expected: FAIL (`ModuleNotFoundError` / missing function).

- [ ] **Step 3: Implement representation recompute service**

```python
def refresh_person_representation(connection: Connection, *, person_id: str) -> None:
    rows = _load_confirmed_embeddings(connection, person_id=person_id)
    if not rows:
        _delete_representation(connection, person_id=person_id)
        return
    centroid = _average_embedding(rows)
    dispersion = _mean_cosine_distance(rows, centroid)
    _upsert_representation(connection, person_id=person_id, centroid=centroid, count=len(rows), dispersion=dispersion)
```

- [ ] **Step 4: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_person_representations_service.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/person_representations.py \
  apps/api/tests/test_person_representations_service.py
git commit -m "feat: add person representation recompute service"
```

### Task 4: Suggestion Scoring/Persistence Service

**Files:**
- Create: `apps/api/app/services/face_suggestions.py`
- Test: `apps/api/tests/test_face_suggestions_service.py`

- [ ] **Step 1: Write failing tests for ranked suggestion snapshots**

```python
def test_refresh_face_suggestions_persists_top_ranked_candidates(tmp_path):
    refresh_face_suggestions_for_face(connection, face_id="face-source", limit=3)
    rows = connection.execute(
        select(face_suggestions).where(face_suggestions.c.face_id == "face-source").order_by(face_suggestions.c.rank)
    ).mappings().all()
    assert [row["person_id"] for row in rows] == ["person-1", "person-2", "person-3"]
    assert rows[0]["confidence"] >= rows[1]["confidence"] >= rows[2]["confidence"]
```

- [ ] **Step 2: Run targeted suggestion-service tests**

Run: `uv run pytest apps/api/tests/test_face_suggestions_service.py -q`  
Expected: FAIL due to missing service.

- [ ] **Step 3: Implement hybrid ranking and atomic snapshot replace**

```python
def refresh_face_suggestions_for_face(connection: Connection, *, face_id: str, limit: int = 5) -> None:
    source = _load_unlabeled_source_face(connection, face_id=face_id)
    candidates = _score_candidates(connection, source_embedding=source.embedding, limit=limit)
    connection.execute(delete(face_suggestions).where(face_suggestions.c.face_id == face_id))
    for rank, candidate in enumerate(candidates, start=1):
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id=str(uuid4()),
                face_id=face_id,
                person_id=candidate.person_id,
                rank=rank,
                confidence=candidate.confidence,
                centroid_distance=candidate.centroid_distance,
                knn_distance=candidate.knn_distance,
                representation_version=candidate.representation_version,
                scoring_version="hybrid-v1",
                model_version="nearest-neighbor-cosine-v1",
                provenance=candidate.provenance,
            )
        )
```

- [ ] **Step 4: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_face_suggestions_service.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/face_suggestions.py \
  apps/api/tests/test_face_suggestions_service.py
git commit -m "feat: persist ranked machine_suggested snapshots for unlabeled faces"
```

### Task 5: Debounced Recompute Trigger on Human-Confirmed Mutations

**Files:**
- Modify: `apps/api/app/services/face_assignment.py`
- Modify: `apps/api/app/db/queue.py`
- Test: `apps/api/tests/test_queue_store.py`
- Test: `apps/api/tests/test_face_assignment_api.py`

- [ ] **Step 1: Write failing tests for recompute enqueue/refresh behavior**

```python
def test_assignment_enqueues_face_suggestion_recompute_request(tmp_path, monkeypatch):
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
        headers={"X-Face-Validation-Role": "contributor"},
    )
    assert response.status_code == 201
    queued = queue_store.list_pending()
    assert any(row.payload_type == "face_suggestion_recompute" for row in queued)
```

```python
def test_queue_refresh_nonprocessing_updates_payload_for_same_person_key(tmp_path):
    old_payload = {"person_id": "person-1", "debounce_until_ts": "2026-05-03T12:00:00+00:00"}
    new_payload = {"person_id": "person-1", "debounce_until_ts": "2026-05-03T12:00:05+00:00"}
    assert updated_row.payload_json["debounce_until_ts"] != original_row.payload_json["debounce_until_ts"]
```

- [ ] **Step 2: Run targeted queue/assignment tests**

Run: `uv run pytest apps/api/tests/test_queue_store.py apps/api/tests/test_face_assignment_api.py -k "recompute or debounce" -q`  
Expected: FAIL on missing queue integration.

- [ ] **Step 3: Implement enqueue helper in face-assignment service**

```python
def _enqueue_face_suggestion_recompute(connection: Connection, *, person_ids: list[str]) -> None:
    queue_store = IngestQueueStore()
    for person_id in sorted(set(person_ids)):
        payload = {
            "person_id": person_id,
            "debounce_until_ts": datetime.now(tz=UTC).isoformat(),
            "reason": "human_confirmed_event",
        }
        result = queue_store.enqueue_in_transaction(
            payload_type="face_suggestion_recompute",
            payload=payload,
            idempotency_key=f"face_suggestion_recompute:{person_id}",
            connection=connection,
        )
        if not result.created:
            queue_store.refresh_nonprocessing_in_transaction(result.ingest_queue_id, payload=payload, connection=connection)
```

- [ ] **Step 4: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_queue_store.py apps/api/tests/test_face_assignment_api.py -k "recompute or debounce" -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/face_assignment.py \
  apps/api/app/db/queue.py \
  apps/api/tests/test_queue_store.py \
  apps/api/tests/test_face_assignment_api.py
git commit -m "feat: enqueue debounced face suggestion recompute after human-confirmed writes"
```

### Task 6: Worker Processing for Recompute Payloads

**Files:**
- Modify: `apps/api/app/services/ingest_queue_processor.py`
- Test: `apps/api/tests/test_ingest_queue_processor.py`

- [ ] **Step 1: Add failing worker test for `face_suggestion_recompute` payload**

```python
def test_process_pending_queue_handles_face_suggestion_recompute_payload(tmp_path):
    payload = {
        "person_id": "person-1",
        "debounce_until_ts": "2026-05-03T12:00:00+00:00",
        "reason": "human_confirmed_event",
    }
    queue_store.enqueue(
        payload_type="face_suggestion_recompute",
        payload=payload,
        idempotency_key="face_suggestion_recompute:person-1",
    )
    result = process_pending_ingest_queue(database_url, limit=10)
    assert result.processed == 1
    assert _load_face_suggestion_rows(database_url, "face-unlabeled")
```

- [ ] **Step 2: Run targeted processor tests**

Run: `uv run pytest apps/api/tests/test_ingest_queue_processor.py -k "face_suggestion_recompute" -q`  
Expected: FAIL with unsupported payload type.

- [ ] **Step 3: Implement recompute payload handler in queue processor**

```python
if claimed_row.payload_type == "face_suggestion_recompute":
    payload = claimed_row.payload_json
    if _debounce_not_elapsed(payload):
        queue_store.mark_completed(claimed_row.ingest_queue_id, connection=connection)
        return None, None
    refresh_person_representation(connection, person_id=str(payload["person_id"]))
    refresh_face_suggestions_for_person_scope(connection, person_id=str(payload["person_id"]))
    return None, None
```

- [ ] **Step 4: Re-run targeted processor tests**

Run: `uv run pytest apps/api/tests/test_ingest_queue_processor.py -k "face_suggestion_recompute" -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ingest_queue_processor.py \
  apps/api/tests/test_ingest_queue_processor.py
git commit -m "feat: process face suggestion recompute payloads in worker queue loop"
```

### Task 7: Certainty-Aware Search Filters and Facets

**Files:**
- Modify: `apps/api/app/schemas/search_request.py`
- Modify: `apps/api/app/repositories/photos_repo.py`
- Modify: `apps/api/app/domain/facets.py`
- Test: `apps/api/tests/test_search_service.py`
- Test: `apps/api/tests/test_facets.py`

- [ ] **Step 1: Add failing tests for `person_certainty_mode` and threshold behavior**

```python
def test_search_repository_person_filter_human_only_excludes_machine_suggested(tmp_path):
    items, total, _ = repo.search_photos(
        filters=SearchFilters(person_names=["inez"], person_certainty_mode="human_only"),
        sort=SortSpec(by="shot_ts", dir="desc"),
        page=PageSpec(limit=50),
    )
    assert [item["photo_id"] for item in items] == ["photo-human"]
```

```python
def test_search_repository_person_filter_include_suggestions_honors_threshold(tmp_path):
    filters = SearchFilters(
        person_names=["inez"],
        person_certainty_mode="include_suggestions",
        suggestion_confidence_min=0.78,
    )
    items, total, _ = repo.search_photos(filters=filters, sort=SortSpec(), page=PageSpec(limit=50))
    assert any(item["photo_id"] == "photo-machine-suggested" for item in items)
```

- [ ] **Step 2: Run targeted search/facet tests**

Run: `uv run pytest apps/api/tests/test_search_service.py apps/api/tests/test_facets.py -k "certainty or suggestion_confidence or people_machine_suggested" -q`  
Expected: FAIL due to missing schema/filters.

- [ ] **Step 3: Implement search schema and repository filtering clauses**

```python
class SearchFilters(BaseModel):
    date: Optional[DateFilter] = None
    camera_make: Optional[List[str]] = None
    extension: Optional[List[str]] = None
    person_certainty_mode: Literal["human_only", "include_suggestions"] | None = None
    suggestion_confidence_min: float | None = None
```

```python
if filters.person_certainty_mode == "human_only":
    # require matching human_confirmed provenance row
elif filters.person_certainty_mode == "include_suggestions":
    # include human_confirmed OR face_suggestions.confidence >= threshold
```

- [ ] **Step 4: Re-run targeted tests**

Run: `uv run pytest apps/api/tests/test_search_service.py apps/api/tests/test_facets.py -k "certainty or suggestion_confidence or people_machine_suggested" -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/schemas/search_request.py \
  apps/api/app/repositories/photos_repo.py \
  apps/api/app/domain/facets.py \
  apps/api/tests/test_search_service.py \
  apps/api/tests/test_facets.py
git commit -m "feat: add certainty-aware person filtering and facets in search"
```

### Task 8: UI Contract Cleanup and Library Certainty Controls

**Files:**
- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
- Modify: `apps/ui/src/pages/FaceBBoxOverlay.tsx`
- Modify: `apps/ui/src/pages/FaceAssignmentControls.tsx`
- Modify: `apps/ui/src/pages/library/libraryRouteTypes.ts`
- Modify: `apps/ui/src/pages/library/libraryRouteSearchState.ts`
- Modify: `apps/ui/src/pages/library/libraryRouteApi.ts`
- Modify: `apps/ui/src/pages/library/LibrarySearchForm.tsx`
- Modify: `apps/ui/src/pages/search/FacetFilterPanel.tsx`
- Modify: `apps/ui/src/pages/search/facetFilters.ts`
- Test: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`
- Test: `apps/ui/src/pages/LibraryRoutePage.test.tsx`
- Create/Modify Test: `apps/ui/src/pages/library/libraryRouteSearchState.test.ts`

- [ ] **Step 1: Add failing UI tests for removed auto-apply payload and certainty filters**

```ts
it("does not auto-assign from candidates payload and only applies on user click", async () => {
  // payload has candidates only; no auto_applied_assignment handling branch
});

it("serializes certainty mode and threshold into search filters", () => {
  expect(buildSearchFilters("", "", ["inez"], null, null, [], "include_suggestions", "0.8")).toEqual({
    person_names: ["inez"],
    person_certainty_mode: "include_suggestions",
    suggestion_confidence_min: 0.8
  });
});
```

- [ ] **Step 2: Run targeted UI tests**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx src/pages/LibraryRoutePage.test.tsx src/pages/library/libraryRouteSearchState.test.ts`  
Expected: FAIL on contract/type mismatches.

- [ ] **Step 3: Implement UI filter state and request payload changes**

```ts
export type PersonCertaintyMode = "human_only" | "include_suggestions";

export function buildSearchFilters(
  fromDate: string,
  toDate: string,
  selectedPersonNames: string[],
  locationRadius: LibraryLocationRadius | null,
  hasFaces: boolean | null,
  pathHints: string[],
  personCertaintyMode: PersonCertaintyMode | null,
  suggestionConfidenceMinDraft: string,
): {
  date?: { from?: string; to?: string };
  person_names?: string[];
  person_certainty_mode?: PersonCertaintyMode;
  suggestion_confidence_min?: number;
} | null {
  const threshold = Number.parseFloat(suggestionConfidenceMinDraft);
  const normalizedThreshold = Number.isFinite(threshold) ? threshold : undefined;
}
```

```tsx
<select aria-label="Person certainty mode" value={personCertaintyMode} onChange={onPersonCertaintyModeChange}>
  <option value="human_only">Human-reviewed only</option>
  <option value="include_suggestions">Include heuristic suggestions</option>
</select>
```

- [ ] **Step 4: Re-run targeted UI tests**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx src/pages/LibraryRoutePage.test.tsx src/pages/library/libraryRouteSearchState.test.ts`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/ui/src/pages/PhotoFaceAssignmentModal.tsx \
  apps/ui/src/pages/FaceBBoxOverlay.tsx \
  apps/ui/src/pages/FaceAssignmentControls.tsx \
  apps/ui/src/pages/library/libraryRouteTypes.ts \
  apps/ui/src/pages/library/libraryRouteSearchState.ts \
  apps/ui/src/pages/library/libraryRouteApi.ts \
  apps/ui/src/pages/library/LibrarySearchForm.tsx \
  apps/ui/src/pages/search/FacetFilterPanel.tsx \
  apps/ui/src/pages/search/facetFilters.ts \
  apps/ui/src/pages/PhotoDetailRoutePage.test.tsx \
  apps/ui/src/pages/LibraryRoutePage.test.tsx \
  apps/ui/src/pages/library/libraryRouteSearchState.test.ts
git commit -m "ui: add certainty-aware person filters and remove auto-apply contract usage"
```

### Task 9: End-to-End Verification and Documentation Sweep

**Files:**
- Modify: `README.md` (only if runtime/filter contract docs changed)
- Verify all changed files from Tasks 1-8

- [ ] **Step 1: Run backend regression suite for touched domains**

Run: `uv run pytest apps/api/tests/test_migrations.py apps/api/tests/test_recognition_policy.py apps/api/tests/test_face_candidates_service.py apps/api/tests/test_face_candidates_api.py apps/api/tests/test_face_assignment_api.py apps/api/tests/test_queue_store.py apps/api/tests/test_ingest_queue_processor.py apps/api/tests/test_search_service.py apps/api/tests/test_facets.py -q`  
Expected: PASS.

- [ ] **Step 2: Run UI regression suite for touched routes**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx src/pages/LibraryRoutePage.test.tsx src/pages/library/libraryRouteSearchState.test.ts`  
Expected: PASS.

- [ ] **Step 3: Run lint/type checks for changed surfaces**

Run: `uv run ruff check apps/api/app apps/api/tests packages/db-schema`  
Expected: PASS.  
Run: `npm --prefix apps/ui run test -- --runInBand`  
Expected: PASS.

- [ ] **Step 4: Final commit for doc touch-ups or test fixture updates**

```bash
git add README.md
git commit -m "docs: describe human-confirmed-only suggestion semantics and certainty filters"
```

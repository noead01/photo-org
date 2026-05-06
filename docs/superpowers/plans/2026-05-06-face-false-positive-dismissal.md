# Face False-Positive Dismissal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a permanent, role-gated false-positive dismissal flow for detected faces from photo detail, and keep dismissed faces out of photo detail and suggestions review reads.

**Architecture:** Persist dismissal state directly on `faces` via `dismissed_ts` and `dismissal_provenance`, expose a new `POST /api/v1/faces/{face_id}/dismissals` endpoint on the existing face-labeling router, and treat only non-dismissed face rows as active in read models. The UI work stays confined to the photo-detail assignment modal and route-local state update path.

**Tech Stack:** FastAPI, SQLAlchemy Core, Alembic initial-schema editing, Pydantic, React 18, TypeScript, Vitest, pytest

---

## File Structure

**Schema and shared definitions**

- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
  - Add `dismissed_ts` and `dismissal_provenance` to the shared `faces` table definition.
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py`
  - Mirror the same columns in the initial migration.

**Backend write path**

- Modify: `apps/api/app/services/face_assignment.py`
  - Add dismissal-specific errors and the service function that marks a face dismissed and clears persisted suggestions.
- Modify: `apps/api/app/routers/face_assignments.py`
  - Add the `POST /faces/{face_id}/dismissals` endpoint and response model.
- Modify: `apps/api/tests/test_face_assignment_api.py`
  - Cover successful dismissal, auth failures, assigned-face conflict, dismissed-face conflict, and suggestion cleanup.

**Backend read filtering**

- Modify: `apps/api/app/repositories/photos_repo.py`
  - Exclude dismissed faces from hydrated photo detail faces and derive `metadata.faces_count` from active faces for detail reads.
- Modify: `apps/api/app/services/face_suggestion_review.py`
  - Exclude dismissed faces from the suggestions review feed queries.
- Modify: `apps/api/tests/test_photo_detail_api.py`
  - Cover detail omission of dismissed faces and active-only face counts.
- Modify: `apps/api/tests/test_face_suggestion_review_api.py`
  - Cover dismissed faces being absent from `/api/v1/suggestions/faces`.

**Frontend photo-detail UX**

- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
  - Add the discard action, dismissal request handling, and error mapping.
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
  - Add local state mutation helper for removing a dismissed face and updating metadata.
- Modify: `apps/ui/src/styles/app-shell.css`
  - Style the destructive dismiss action in the modal.
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`
  - Cover the discard action, successful local removal, and permission/conflict error handling.

## Task 1: Add Dismissal Schema and API Contract

**Files:**
- Modify: `packages/db-schema/photoorg_db_schema/schema.py:183-199`
- Modify: `apps/api/alembic/versions/20260321_000001_initial_schema.py:275-290`
- Modify: `apps/api/app/services/face_assignment.py:1-398`
- Modify: `apps/api/app/routers/face_assignments.py:1-314`
- Modify: `apps/api/tests/test_face_assignment_api.py`

- [ ] **Step 1: Write the failing API tests**

```python
from app.storage import face_labels, face_suggestions, faces, ingest_queue, people, photos


def test_face_dismissal_api_marks_unassigned_face_as_dismissed_and_clears_suggestions(
    tmp_path, monkeypatch
):
    database_url = _database_url(tmp_path, "face-dismiss.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
            )
        )
        connection.execute(
            insert(face_suggestions).values(
                face_suggestion_id="suggestion-1",
                face_id="face-1",
                person_id="person-1",
                rank=1,
                confidence=0.91,
                centroid_distance=0.09,
                knn_distance=0.09,
                representation_version=1,
                scoring_version="hybrid-v1",
                model_version="recognition-v1",
            )
        )

    client = _authorized_client()
    response = client.post("/api/v1/faces/face-1/dismissals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["face_id"] == "face-1"
    assert payload["photo_id"] == "photo-1"
    assert payload["dismissed_ts"].endswith("Z")

    with engine.connect() as connection:
        face_row = connection.execute(
            select(
                faces.c.dismissed_ts,
                faces.c.dismissal_provenance,
            ).where(faces.c.face_id == "face-1")
        ).mappings().one()
        persisted_suggestions = connection.execute(
            select(face_suggestions.c.face_suggestion_id).where(face_suggestions.c.face_id == "face-1")
        ).all()

    assert face_row["dismissed_ts"] is not None
    assert face_row["dismissal_provenance"] == {
        "workflow": "face-labeling",
        "surface": "api",
        "action": "dismiss_false_positive",
    }
    assert persisted_suggestions == []


def test_face_dismissal_api_rejects_already_assigned_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-dismiss-assigned.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id="person-1",
            )
        )

    client = _authorized_client()
    response = client.post("/api/v1/faces/face-1/dismissals")

    assert response.status_code == 409
    assert response.json() == {"detail": "Face already assigned"}


def test_face_dismissal_api_rejects_already_dismissed_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "face-dismiss-dismissed.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-1",
                person_id=None,
                dismissed_ts=now,
                dismissal_provenance={"workflow": "face-labeling", "surface": "api", "action": "dismiss_false_positive"},
            )
        )

    client = _authorized_client()
    response = client.post("/api/v1/faces/face-1/dismissals")

    assert response.status_code == 409
    assert response.json() == {"detail": "Face already dismissed"}
```

- [ ] **Step 2: Run the API dismissal tests to verify they fail**

Run: `uv run pytest apps/api/tests/test_face_assignment_api.py -k dismissal -q`

Expected: `FAIL` because `faces.dismissed_ts` / `faces.dismissal_provenance` do not exist yet and `POST /api/v1/faces/{face_id}/dismissals` is not implemented.

- [ ] **Step 3: Add the shared schema columns**

```python
faces = Table(
    "faces",
    metadata,
    Column("face_id", String(36), primary_key=True),
    Column("photo_id", String(36), ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
    Column("person_id", String(36), ForeignKey("people.person_id", ondelete="RESTRICT")),
    Column("bbox_x", Integer),
    Column("bbox_y", Integer),
    Column("bbox_w", Integer),
    Column("bbox_h", Integer),
    Column("bitmap", LargeBinary),
    Column("embedding", JSON()),
    Column("detector_name", String),
    Column("detector_version", String),
    Column("provenance", JSON()),
    Column("dismissed_ts", TIMESTAMP(timezone=True)),
    Column("dismissal_provenance", JSON()),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)
```

```python
op.create_table(
    "faces",
    sa.Column("face_id", sa.String(36), primary_key=True),
    sa.Column("photo_id", sa.String(36), sa.ForeignKey("photos.photo_id", ondelete="CASCADE"), nullable=False),
    sa.Column("person_id", sa.String(36), sa.ForeignKey("people.person_id", ondelete="RESTRICT"), nullable=True),
    sa.Column("bbox_x", sa.Integer(), nullable=True),
    sa.Column("bbox_y", sa.Integer(), nullable=True),
    sa.Column("bbox_w", sa.Integer(), nullable=True),
    sa.Column("bbox_h", sa.Integer(), nullable=True),
    sa.Column("bitmap", sa.LargeBinary(), nullable=True),
    sa.Column("embedding", embedding_type, nullable=True),
    sa.Column("detector_name", sa.String(), nullable=True),
    sa.Column("detector_version", sa.String(), nullable=True),
    sa.Column("provenance", sa.JSON(), nullable=True),
    sa.Column("dismissed_ts", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("dismissal_provenance", sa.JSON(), nullable=True),
    sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
)
```

- [ ] **Step 4: Implement the dismissal service and router contract**

```python
class FaceAlreadyDismissedError(RuntimeError):
    pass


def dismiss_false_positive_face(
    connection: Connection,
    *,
    face_id: str,
) -> dict[str, str]:
    row = (
        connection.execute(
            select(
                faces.c.face_id,
                faces.c.photo_id,
                faces.c.person_id,
                faces.c.dismissed_ts,
            ).where(faces.c.face_id == face_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise FaceNotFoundError("Face not found")
    if row["person_id"] is not None:
        raise FaceAlreadyAssignedError("Face already assigned")
    if row["dismissed_ts"] is not None:
        raise FaceAlreadyDismissedError("Face already dismissed")

    dismissed_ts = datetime.now(UTC)
    connection.execute(
        update(faces)
        .where(faces.c.face_id == face_id, faces.c.person_id.is_(None), faces.c.dismissed_ts.is_(None))
        .values(
            dismissed_ts=dismissed_ts,
            dismissal_provenance={
                "workflow": "face-labeling",
                "surface": "api",
                "action": "dismiss_false_positive",
            },
        )
    )
    connection.execute(delete(face_suggestions).where(face_suggestions.c.face_id == face_id))
    return {
        "face_id": str(row["face_id"]),
        "photo_id": str(row["photo_id"]),
        "dismissed_ts": dismissed_ts.isoformat().replace("+00:00", "Z"),
    }
```

```python
class FaceDismissalResponse(BaseModel):
    face_id: str
    photo_id: str
    dismissed_ts: str


@router.post(
    "/{face_id}/dismissals",
    summary="Dismiss false-positive face detection",
    description="Persistently dismiss an unassigned detected face that does not correspond to a real face.",
    response_model=FaceDismissalResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Face validation role required"},
        status.HTTP_404_NOT_FOUND: {"description": "Face not found"},
        status.HTTP_409_CONFLICT: {"description": "Face already assigned or already dismissed"},
    },
)
def dismiss_face_endpoint(
    face_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_face_validation_role),
) -> FaceDismissalResponse:
    try:
        result = dismiss_false_positive_face(db.connection(), face_id=face_id)
    except FaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FaceAlreadyAssignedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except FaceAlreadyDismissedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return FaceDismissalResponse.model_validate(result)
```

- [ ] **Step 5: Run the dismissal API tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_face_assignment_api.py -k dismissal -q`

Expected: `PASS`

- [ ] **Step 6: Commit the backend dismissal contract**

```bash
git add packages/db-schema/photoorg_db_schema/schema.py \
  apps/api/alembic/versions/20260321_000001_initial_schema.py \
  apps/api/app/services/face_assignment.py \
  apps/api/app/routers/face_assignments.py \
  apps/api/tests/test_face_assignment_api.py
git commit -m "feat: add false-positive face dismissal api"
```

## Task 2: Filter Dismissed Faces from Photo Detail

**Files:**
- Modify: `apps/api/app/repositories/photos_repo.py:781-977`
- Modify: `apps/api/tests/test_photo_detail_api.py`

- [ ] **Step 1: Write the failing photo-detail tests**

```python
def test_photo_detail_api_omits_dismissed_faces_and_recomputes_active_face_count(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'photo-detail-api-dismissed-faces.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(photos).values(
                photo_id="photo-1",
                sha256="sha-1",
                created_ts=now,
                updated_ts=now,
                path="/photos/photo-1.jpg",
                filesize=1024,
                ext="jpg",
                faces_count=2,
            )
        )
        connection.execute(
            insert(faces),
            [
                {
                    "face_id": "face-active",
                    "photo_id": "photo-1",
                    "person_id": None,
                    "bbox_x": 10,
                    "bbox_y": 20,
                    "bbox_w": 30,
                    "bbox_h": 40,
                },
                {
                    "face_id": "face-dismissed",
                    "photo_id": "photo-1",
                    "person_id": None,
                    "bbox_x": 50,
                    "bbox_y": 60,
                    "bbox_w": 70,
                    "bbox_h": 80,
                    "dismissed_ts": now,
                    "dismissal_provenance": {
                        "workflow": "face-labeling",
                        "surface": "api",
                        "action": "dismiss_false_positive",
                    },
                },
            ],
        )

    client = TestClient(app)
    response = client.get("/api/v1/photos/photo-1")

    assert response.status_code == 200
    payload = response.json()
    assert [face["face_id"] for face in payload["faces"]] == ["face-active"]
    assert payload["metadata"]["faces_count"] == 1
```

- [ ] **Step 2: Run the photo-detail dismissal test to verify it fails**

Run: `uv run pytest apps/api/tests/test_photo_detail_api.py -k dismissed_faces -q`

Expected: `FAIL` because dismissed face rows are still hydrated and `metadata.faces_count` still mirrors the stored `photos.faces_count`.

- [ ] **Step 3: Filter dismissed faces and derive active face count in the repository**

```python
face_rows = self.db.execute(
    select(*face_columns)
    .where(
        self.faces.c.photo_id.in_(pids),
        self.faces.c.dismissed_ts.is_(None),
    )
    .order_by(self.faces.c.photo_id, self.faces.c.face_id)
).all()
```

```python
item = self._hydrate_items(rows, include_face_regions=True)[0]
row = rows[0]
item["metadata"] = {
    "sha256": row.sha256,
    "phash": row.phash,
    "shot_ts_source": self._normalize_shot_ts_source_label(
        row.shot_ts_source,
        exif_attributes=exif_attributes,
    ),
    "camera_model": row.camera_model,
    "software": row.software,
    "gps_latitude": row.gps_latitude,
    "gps_longitude": row.gps_longitude,
    "gps_altitude": row.gps_altitude,
    "exif_attributes": exif_attributes,
    "exif_unmapped_attributes": exif_unmapped_attributes,
    "created_ts": row.created_ts,
    "updated_ts": row.updated_ts,
    "modified_ts": row.modified_ts,
    "deleted_ts": row.deleted_ts,
    "faces_count": len(item["faces"]),
    "faces_detected_ts": row.faces_detected_ts,
}
```

- [ ] **Step 4: Run the photo-detail tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_photo_detail_api.py -k "dismissed_faces or projected_metadata" -q`

Expected: `PASS`

- [ ] **Step 5: Commit the photo-detail read filtering**

```bash
git add apps/api/app/repositories/photos_repo.py apps/api/tests/test_photo_detail_api.py
git commit -m "feat: hide dismissed faces from photo detail"
```

## Task 3: Filter Dismissed Faces from Suggestions Review

**Files:**
- Modify: `apps/api/app/services/face_suggestion_review.py:159-330`
- Modify: `apps/api/tests/test_face_suggestion_review_api.py`

- [ ] **Step 1: Write the failing suggestions-review test**

```python
def test_face_suggestion_review_list_omits_dismissed_faces(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "face-suggestion-review-dismissed.db")

    engine = create_engine(f"sqlite:///{tmp_path / 'face-suggestion-review-dismissed.db'}", future=True)
    now = datetime(2026, 5, 6, 12, 0, tzinfo=UTC)
    with engine.begin() as connection:
        _insert_person(connection, person_id="person-1", display_name="Alex")
        _insert_photo(
            connection,
            photo_id="photo-1",
            path="/photos/1.jpg",
            shot_ts=datetime(2026, 5, 5, 11, 0, tzinfo=UTC),
        )
        connection.execute(
            insert(faces),
            [
                {"face_id": "face-active", "photo_id": "photo-1", "person_id": None},
                {
                    "face_id": "face-dismissed",
                    "photo_id": "photo-1",
                    "person_id": None,
                    "dismissed_ts": now,
                    "dismissal_provenance": {
                        "workflow": "face-labeling",
                        "surface": "api",
                        "action": "dismiss_false_positive",
                    },
                },
            ],
        )
        connection.execute(
            insert(face_suggestions),
            [
                {
                    "face_suggestion_id": "s1",
                    "face_id": "face-active",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.95,
                    "centroid_distance": 0.05,
                    "knn_distance": 0.05,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
                {
                    "face_suggestion_id": "s2",
                    "face_id": "face-dismissed",
                    "person_id": "person-1",
                    "rank": 1,
                    "confidence": 0.96,
                    "centroid_distance": 0.04,
                    "knn_distance": 0.04,
                    "representation_version": 2,
                    "scoring_version": "hybrid-v1",
                    "model_version": "recognition-v1",
                },
            ],
        )

    response = client.get("/api/v1/suggestions/faces", params={"page": 1, "page_size": 24})

    assert response.status_code == 200
    payload = response.json()
    assert payload["page"]["total_items"] == 1
    assert [face["face_id"] for face in payload["items"][0]["faces"]] == ["face-active"]
```

- [ ] **Step 2: Run the suggestions-review test to verify it fails**

Run: `uv run pytest apps/api/tests/test_face_suggestion_review_api.py -k omitted_dismissed -q`

Expected: `FAIL` because the current eligible-photo and face-row queries do not filter on `faces.dismissed_ts`.

- [ ] **Step 3: Add `dismissed_ts IS NULL` to the review-feed queries**

```python
eligible_photo_ids = (
    select(faces.c.photo_id)
    .select_from(
        faces.join(top_suggestion, top_suggestion.c.face_id == faces.c.face_id).join(
            photos, photos.c.photo_id == faces.c.photo_id
        )
    )
    .where(
        faces.c.person_id.is_(None),
        faces.c.dismissed_ts.is_(None),
        photos.c.deleted_ts.is_(None),
        top_suggestion.c.confidence >= normalized_min_confidence,
    )
    .distinct()
    .subquery()
)
```

```python
face_rows = (
    connection.execute(
        select(
            faces.c.photo_id,
            faces.c.face_id,
            faces.c.bbox_x,
            faces.c.bbox_y,
            faces.c.bbox_w,
            faces.c.bbox_h,
            faces.c.provenance,
            top_suggestion.c.person_id.label("suggested_person_id"),
            top_suggestion.c.confidence.label("suggested_confidence"),
            people.c.display_name.label("suggested_display_name"),
        )
        .select_from(
            faces.join(top_suggestion, top_suggestion.c.face_id == faces.c.face_id).join(
                people, people.c.person_id == top_suggestion.c.person_id
            )
        )
        .where(
            faces.c.photo_id.in_(photo_ids),
            faces.c.person_id.is_(None),
            faces.c.dismissed_ts.is_(None),
            top_suggestion.c.confidence >= normalized_min_confidence,
        )
        .order_by(faces.c.photo_id.asc(), faces.c.face_id.asc())
    )
    .mappings()
    .all()
)
```

- [ ] **Step 4: Run the suggestions-review tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_face_suggestion_review_api.py -q`

Expected: `PASS`

- [ ] **Step 5: Commit the suggestions-review filtering**

```bash
git add apps/api/app/services/face_suggestion_review.py apps/api/tests/test_face_suggestion_review_api.py
git commit -m "feat: exclude dismissed faces from suggestions review"
```

## Task 4: Add the Photo-Detail Modal Dismiss Action and Local State Update

**Files:**
- Modify: `apps/ui/src/pages/PhotoFaceAssignmentModal.tsx`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.tsx`
- Modify: `apps/ui/src/styles/app-shell.css`
- Modify: `apps/ui/src/pages/PhotoDetailRoutePage.test.tsx`

- [ ] **Step 1: Write the failing photo-detail UI tests**

```tsx
it("dismisses an unlabeled false-positive face from the detail modal and removes it locally", async () => {
  const user = userEvent.setup();

  fetchMock
    .mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          faces: [
            {
              face_id: "face-1",
              person_id: null,
              bbox_x: 10,
              bbox_y: 10,
              bbox_w: 20,
              bbox_h: 20,
              label_source: null,
              confidence: null,
              model_version: null,
              provenance: null,
              label_recorded_ts: null
            }
          ]
        })
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => []
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        face_id: "face-1",
        candidates: [],
        suggestion_policy: {
          decision: "no_suggestion",
          review_threshold: 0.5,
          auto_accept_threshold: 0.9,
          top_candidate_confidence: null
        },
        review_needed_suggestion: null
      })
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        face_id: "face-1",
        photo_id: "photo-1",
        dismissed_ts: "2026-05-06T12:00:00Z"
      })
    } as Response);

  renderDetail();

  await user.click(await screen.findByRole("button", { name: "Open face assignment for face region 1" }));
  await user.click(await screen.findByRole("button", { name: "Discard false positive" }));

  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: "Face assignment" })).not.toBeInTheDocument();
  });
  expect(screen.queryByRole("button", { name: "Open face assignment for face region 1" })).not.toBeInTheDocument();
  expect(screen.getByText("No face regions detected for this photo.")).toBeInTheDocument();
});


it("shows the dismissal permission error inline in the detail modal", async () => {
  const user = userEvent.setup();

  fetchMock
    .mockResolvedValueOnce({
      ok: true,
      json: async () =>
        buildPayload({
          faces: [
            {
              face_id: "face-1",
              person_id: null,
              bbox_x: 10,
              bbox_y: 10,
              bbox_w: 20,
              bbox_h: 20,
              label_source: null,
              confidence: null,
              model_version: null,
              provenance: null,
              label_recorded_ts: null
            }
          ]
        })
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => []
    } as Response)
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        face_id: "face-1",
        candidates: [],
        suggestion_policy: {
          decision: "no_suggestion",
          review_threshold: 0.5,
          auto_accept_threshold: 0.9,
          top_candidate_confidence: null
        },
        review_needed_suggestion: null
      })
    } as Response)
    .mockResolvedValueOnce({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Face validation role required" })
    } as Response);

  renderDetail();

  await user.click(await screen.findByRole("button", { name: "Open face assignment for face region 1" }));
  await user.click(await screen.findByRole("button", { name: "Discard false positive" }));

  expect(await screen.findByText("You do not have permission to discard faces.")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the photo-detail UI tests to verify they fail**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx`

Expected: `FAIL` because the modal does not render a dismiss action and the detail route has no local “remove dismissed face” state transition.

- [ ] **Step 3: Implement the modal dismissal request and route-local removal helper**

```tsx
function mapDismissalError(status: number, detail: string | null): string {
  if (status === 403) {
    return "You do not have permission to discard faces.";
  }
  if (status === 404) {
    return detail ?? "Face no longer exists.";
  }
  if (status === 409) {
    return detail ?? "Face dismissal could not be applied.";
  }
  return `Dismissal request failed (${status}).`;
}
```

```tsx
interface PhotoFaceAssignmentModalProps {
  isOpen: boolean;
  face: (FaceAssignmentModalFace & { sequence: number }) | null;
  region: FaceOverlayRegion | null;
  thumbnail: FaceThumbnail | null;
  people: FaceAssignmentModalPerson[];
  onClose: () => void;
  onFaceUpdated: (faceId: string, personId: string) => void;
  onFaceDismissed: (faceId: string) => void;
  onPersonCreated: (person: FaceAssignmentModalPerson) => void;
}
```

```tsx
async function dismissFalsePositive() {
  if (!face || face.person_id !== null || isSubmitting) {
    return;
  }

  setIsSubmitting(true);
  setError(null);
  try {
    const response = await fetch(`/api/v1/faces/${face.face_id}/dismissals`, {
      method: "POST",
      headers: {
        "X-Face-Validation-Role": "contributor"
      }
    });
    if (!response.ok) {
      const detail = await readErrorDetail(response);
      setError(mapDismissalError(response.status, detail));
      return;
    }
    onFaceDismissed(face.face_id);
    onClose();
  } catch {
    setError("Could not discard face.");
  } finally {
    setIsSubmitting(false);
  }
}
```

```tsx
{face.person_id === null ? (
  <button
    type="button"
    className="face-assignment-modal-dismiss"
    onClick={() => void dismissFalsePositive()}
    disabled={isBusy}
  >
    Discard false positive
  </button>
) : null}
```

```tsx
function applyFaceDismissal(detail: PhotoDetailPayload, faceId: string): PhotoDetailPayload {
  const nextFaces = detail.faces.filter((face) => face.face_id !== faceId);
  const nextPeople = Array.from(
    new Set(
      nextFaces
        .map((face) => face.person_id)
        .filter((value): value is string => value !== null)
    )
  );

  return {
    ...detail,
    faces: nextFaces,
    people: nextPeople,
    metadata: {
      ...detail.metadata,
      faces_count: nextFaces.length
    }
  };
}
```

```tsx
function handleFaceDismissed(faceId: string) {
  setDetail((current) => (current ? applyFaceDismissal(current, faceId) : current));
  setActiveFaceModalId((current) => (current === faceId ? null : current));
}
```

```tsx
<PhotoFaceAssignmentModal
  isOpen={selectedFaceForModal !== null}
  face={selectedFaceForModal}
  region={selectedRegionForModal}
  thumbnail={detail?.thumbnail ?? null}
  people={peopleDirectory.map((person) => ({
    person_id: person.person_id,
    display_name: person.display_name,
    created_ts: person.created_ts,
    updated_ts: person.updated_ts
  }))}
  onClose={() => setActiveFaceModalId(null)}
  onFaceUpdated={handleFaceAssigned}
  onFaceDismissed={handleFaceDismissed}
  onPersonCreated={handlePersonCreated}
/>
```

```css
.face-assignment-modal-dismiss {
  border: 1px solid #fecaca;
  background: #fff1f2;
  color: #b91c1c;
}
```

- [ ] **Step 4: Run the photo-detail UI tests to verify they pass**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx`

Expected: `PASS`

- [ ] **Step 5: Commit the photo-detail dismissal UX**

```bash
git add apps/ui/src/pages/PhotoFaceAssignmentModal.tsx \
  apps/ui/src/pages/PhotoDetailRoutePage.tsx \
  apps/ui/src/styles/app-shell.css \
  apps/ui/src/pages/PhotoDetailRoutePage.test.tsx
git commit -m "feat: add false-positive dismissal to photo detail"
```

## Task 5: Final Verification

**Files:**
- No code changes expected

- [ ] **Step 1: Run the targeted backend verification suite**

Run: `uv run pytest apps/api/tests/test_face_assignment_api.py apps/api/tests/test_photo_detail_api.py apps/api/tests/test_face_suggestion_review_api.py -q`

Expected: `PASS`

- [ ] **Step 2: Run the targeted frontend verification suite**

Run: `npm --prefix apps/ui test -- src/pages/PhotoDetailRoutePage.test.tsx`

Expected: `PASS`

- [ ] **Step 3: Commit only if verification required follow-up edits**

```bash
git status --short
```

Expected: no unexpected modified files beyond this feature scope.

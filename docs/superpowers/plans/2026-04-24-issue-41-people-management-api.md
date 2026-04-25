# Issue 41 People Management API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend people-management model/service/API support for Phase 4 issue #41.

**Architecture:** Use the existing `people` table as the persistence model and add a narrow `app.services.people` service boundary for people CRUD behavior. Expose that service through a new FastAPI router at `/api/v1/people`, with conservative delete checks against existing face and label references.

**Tech Stack:** Python, FastAPI, Pydantic v2, SQLAlchemy Core, Alembic migrations already present, pytest, FastAPI TestClient

---

## File Map

**Create:**

- `apps/api/app/services/people.py`
  Own people-record mutation, lookup, deterministic ordering, display-name normalization, and delete safety checks.
- `apps/api/app/routers/people.py`
  Expose `/api/v1/people` request/response models and HTTP routes.
- `apps/api/tests/test_people_api.py`
  Cover the API contract and SQLite-backed persistence behavior.

**Modify:**

- `apps/api/app/main.py`
  Register the people router and add the OpenAPI `people` tag.

**No schema changes expected:**

- `packages/db-schema/photoorg_db_schema/schema.py`
- `apps/api/alembic/versions/20260321_000001_initial_schema.py`

The current `people` table already has `person_id`, `display_name`, `created_ts`, and `updated_ts`.

### Task 1: Add Create, List, Get, And OpenAPI Contract

**Files:**
- Create: `apps/api/tests/test_people_api.py`
- Create: `apps/api/app/services/people.py`
- Create: `apps/api/app/routers/people.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Write the failing API tests for create, validation, list, get, and OpenAPI registration**

Create `apps/api/tests/test_people_api.py` with this content:

```python
from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import people


def _client(tmp_path, monkeypatch, filename: str) -> TestClient:
    database_url = f"sqlite:///{tmp_path / filename}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()
    return TestClient(app)


def _database_url(tmp_path, filename: str) -> str:
    return f"sqlite:///{tmp_path / filename}"


def test_people_create_api_trims_display_name_and_returns_created_record(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-create.db")

    response = client.post("/api/v1/people", json={"display_name": "  Jane Doe  "})

    assert response.status_code == 201
    payload = response.json()
    assert payload["person_id"]
    assert payload["display_name"] == "Jane Doe"
    assert payload["created_ts"]
    assert payload["updated_ts"] == payload["created_ts"]


def test_people_create_api_rejects_blank_display_name(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-create-blank.db")

    response = client.post("/api/v1/people", json={"display_name": "   "})

    assert response.status_code == 422
    assert any(error["loc"][-1] == "display_name" for error in response.json()["detail"])


def test_people_list_api_orders_by_display_name_then_person_id(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-list.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(people),
            [
                {
                    "person_id": "person-b",
                    "display_name": "Alex",
                    "created_ts": now,
                    "updated_ts": now,
                },
                {
                    "person_id": "person-c",
                    "display_name": "Bea",
                    "created_ts": now,
                    "updated_ts": now,
                },
                {
                    "person_id": "person-a",
                    "display_name": "Alex",
                    "created_ts": now,
                    "updated_ts": now,
                },
            ],
        )

    client = TestClient(app)
    response = client.get("/api/v1/people")

    assert response.status_code == 200
    assert [item["person_id"] for item in response.json()] == [
        "person-a",
        "person-b",
        "person-c",
    ]


def test_people_get_api_returns_existing_person(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-get.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            insert(people).values(
                person_id="person-1",
                display_name="Jane Doe",
                created_ts=now,
                updated_ts=now,
            )
        )

    client = TestClient(app)
    response = client.get("/api/v1/people/person-1")

    assert response.status_code == 200
    assert response.json()["person_id"] == "person-1"
    assert response.json()["display_name"] == "Jane Doe"


def test_people_get_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-get-missing.db")

    response = client.get("/api/v1/people/missing-person")

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_openapi_schema_includes_people_tag_and_paths(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-openapi.db")

    schema = client.get("/openapi.json").json()

    assert any(tag["name"] == "people" for tag in schema["tags"])
    assert "/api/v1/people" in schema["paths"]
    assert "/api/v1/people/{person_id}" in schema["paths"]
```

- [ ] **Step 2: Run the new tests and verify they fail for the expected reason**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -q
```

Expected: tests fail because `/api/v1/people` is not registered yet and the OpenAPI schema does not include the people tag or paths.

- [ ] **Step 3: Add the initial people service**

Create `apps/api/app/services/people.py` with this content:

```python
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from app.storage import people


class PersonNotFoundError(LookupError):
    pass


def _normalize_display_name(display_name: str) -> str:
    return display_name.strip()


def create_person(
    connection: Connection,
    *,
    display_name: str,
    now: datetime,
) -> dict[str, object]:
    normalized_name = _normalize_display_name(display_name)
    values = {
        "person_id": str(uuid4()),
        "display_name": normalized_name,
        "created_ts": now,
        "updated_ts": now,
    }
    connection.execute(insert(people).values(**values))
    return values


def list_people(connection: Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        select(people).order_by(people.c.display_name, people.c.person_id)
    ).mappings()
    return [dict(row) for row in rows]


def get_person(
    connection: Connection,
    person_id: str,
) -> dict[str, object] | None:
    row = connection.execute(
        select(people).where(people.c.person_id == person_id)
    ).mappings().first()
    if row is None:
        return None
    return dict(row)
```

- [ ] **Step 4: Add the initial people router**

Create `apps/api/app/routers/people.py` with this content:

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.services.people import create_person, get_person, list_people


router = APIRouter(prefix="/people", tags=["people"])

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    Field(description="Human-readable name for a person record."),
]


class CreatePersonRequest(BaseModel):
    """Create a person record for face-labeling workflows."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Create a person identity that faces can be assigned to later."
        }
    )

    display_name: DisplayName


class PersonResponse(BaseModel):
    """Canonical person record."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Person identity and lifecycle timestamps."
        }
    )

    person_id: str
    display_name: str
    created_ts: datetime
    updated_ts: datetime


@router.post(
    "",
    summary="Create person",
    description="Create a person record for future face-labeling workflows.",
    response_model=PersonResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_person_route(
    body: CreatePersonRequest,
    db: Session = Depends(get_db),
) -> PersonResponse:
    row = create_person(
        db.connection(),
        display_name=body.display_name,
        now=datetime.now(tz=UTC),
    )
    db.commit()
    return PersonResponse.model_validate(row)


@router.get(
    "",
    summary="List people",
    description="Return all people records in deterministic display order.",
    response_model=list[PersonResponse],
)
def list_people_route(
    db: Session = Depends(get_db),
) -> list[PersonResponse]:
    rows = list_people(db.connection())
    return [PersonResponse.model_validate(row) for row in rows]


@router.get(
    "/{person_id}",
    summary="Get person",
    description="Return a single person record.",
    response_model=PersonResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Person not found"}},
)
def get_person_route(
    person_id: str,
    db: Session = Depends(get_db),
) -> PersonResponse:
    row = get_person(db.connection(), person_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return PersonResponse.model_validate(row)
```

- [ ] **Step 5: Register the people router and OpenAPI tag**

Modify `apps/api/app/main.py`.

Add this import with the other router imports:

```python
from app.routers.people import router as people_router
```

Add this tag entry inside `openapi_tags`, after `search` and before `storage-sources`:

```python
        {
            "name": "people",
            "description": "Create and manage people identities used by face-labeling workflows.",
        },
```

Add this router registration before `photos_router`:

```python
app.include_router(people_router, prefix="/api/v1")
```

- [ ] **Step 6: Run the Task 1 tests and verify they pass**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -q
```

Expected: `6 passed`.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add apps/api/app/main.py apps/api/app/routers/people.py apps/api/app/services/people.py apps/api/tests/test_people_api.py
git commit -m "feat(api): add people create list get api"
```

### Task 2: Add Rename Support

**Files:**
- Modify: `apps/api/tests/test_people_api.py`
- Modify: `apps/api/app/services/people.py`
- Modify: `apps/api/app/routers/people.py`

- [ ] **Step 1: Write the failing update tests**

Modify the SQLAlchemy import in `apps/api/tests/test_people_api.py`:

```python
from sqlalchemy import create_engine, insert, update
```

Append these tests to `apps/api/tests/test_people_api.py`:

```python
def test_people_update_api_renames_person_and_refreshes_updated_timestamp(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-update.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    created = client.post("/api/v1/people", json={"display_name": "Jane Doe"}).json()

    old_ts = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            update(people)
            .where(people.c.person_id == created["person_id"])
            .values(created_ts=old_ts, updated_ts=old_ts)
        )

    response = client.patch(
        f"/api/v1/people/{created['person_id']}",
        json={"display_name": "  Jane Smith  "},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["person_id"] == created["person_id"]
    assert payload["display_name"] == "Jane Smith"
    assert payload["created_ts"].startswith("2026-01-01T12:00:00")
    assert payload["updated_ts"] != payload["created_ts"]


def test_people_update_api_rejects_blank_display_name(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-update-blank.db")
    created = client.post("/api/v1/people", json={"display_name": "Jane Doe"}).json()

    response = client.patch(
        f"/api/v1/people/{created['person_id']}",
        json={"display_name": "  "},
    )

    assert response.status_code == 422
    assert any(error["loc"][-1] == "display_name" for error in response.json()["detail"])


def test_people_update_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-update-missing.db")

    response = client.patch(
        "/api/v1/people/missing-person",
        json={"display_name": "Jane Smith"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"
```

- [ ] **Step 2: Run the update tests and verify they fail**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -k "update_api" -q
```

Expected: tests fail because `PATCH /api/v1/people/{person_id}` is not implemented.

- [ ] **Step 3: Add update support to the service**

Modify the SQLAlchemy import in `apps/api/app/services/people.py`:

```python
from sqlalchemy import insert, select, update
```

Append this function to `apps/api/app/services/people.py`:

```python
def update_person(
    connection: Connection,
    *,
    person_id: str,
    display_name: str,
    now: datetime,
) -> dict[str, object]:
    existing = get_person(connection, person_id)
    if existing is None:
        raise PersonNotFoundError("Person not found")

    values = {
        "display_name": _normalize_display_name(display_name),
        "updated_ts": now,
    }
    connection.execute(
        update(people)
        .where(people.c.person_id == person_id)
        .values(**values)
    )
    return {
        **existing,
        **values,
    }
```

- [ ] **Step 4: Add update support to the router**

Modify the service import in `apps/api/app/routers/people.py`:

```python
from app.services.people import (
    PersonNotFoundError,
    create_person,
    get_person,
    list_people,
    update_person,
)
```

Add this request model after `CreatePersonRequest`:

```python
class UpdatePersonRequest(BaseModel):
    """Update a person record."""

    model_config = ConfigDict(
        json_schema_extra={
            "description": "Rename a person identity without changing its stable identifier."
        }
    )

    display_name: DisplayName
```

Append this route to `apps/api/app/routers/people.py`:

```python
@router.patch(
    "/{person_id}",
    summary="Update person",
    description="Rename an existing person record.",
    response_model=PersonResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Person not found"}},
)
def update_person_route(
    person_id: str,
    body: UpdatePersonRequest,
    db: Session = Depends(get_db),
) -> PersonResponse:
    try:
        row = update_person(
            db.connection(),
            person_id=person_id,
            display_name=body.display_name,
            now=datetime.now(tz=UTC),
        )
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    db.commit()
    return PersonResponse.model_validate(row)
```

- [ ] **Step 5: Run the update tests and full people API file**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -k "update_api" -q
uv run python -m pytest apps/api/tests/test_people_api.py -q
```

Expected: update slice passes, then the full `test_people_api.py` passes with `9 passed`.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add apps/api/app/routers/people.py apps/api/app/services/people.py apps/api/tests/test_people_api.py
git commit -m "feat(api): add people rename endpoint"
```

### Task 3: Add Conservative Delete Support

**Files:**
- Modify: `apps/api/tests/test_people_api.py`
- Modify: `apps/api/app/services/people.py`
- Modify: `apps/api/app/routers/people.py`

- [ ] **Step 1: Write the failing delete tests**

Modify the storage import in `apps/api/tests/test_people_api.py`:

```python
from app.storage import face_labels, faces, people, photos
```

Append these helper functions and tests to `apps/api/tests/test_people_api.py`:

```python
def _insert_photo(connection, *, photo_id: str) -> None:
    now = datetime(2026, 4, 24, 12, 0, tzinfo=UTC)
    connection.execute(
        insert(photos).values(
            photo_id=photo_id,
            sha256=f"{photo_id:0<64}"[:64],
            path=f"/library/{photo_id}.jpg",
            created_ts=now,
            updated_ts=now,
            ext="jpg",
            filesize=123,
        )
    )


def test_people_delete_api_removes_unreferenced_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-delete.db")
    created = client.post("/api/v1/people", json={"display_name": "Jane Doe"}).json()

    response = client.delete(f"/api/v1/people/{created['person_id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/v1/people/{created['person_id']}").status_code == 404


def test_people_delete_api_returns_404_for_missing_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, "people-delete-missing.db")

    response = client.delete("/api/v1/people/missing-person")

    assert response.status_code == 404
    assert response.json()["detail"] == "Person not found"


def test_people_delete_api_returns_409_when_person_is_referenced_by_face(tmp_path, monkeypatch):
    database_url = _database_url(tmp_path, "people-delete-face-reference.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    created = client.post("/api/v1/people", json={"display_name": "Jane Doe"}).json()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-face-ref")
        connection.execute(
            insert(faces).values(
                face_id="face-1",
                photo_id="photo-face-ref",
                person_id=created["person_id"],
                bbox_x=1,
                bbox_y=2,
                bbox_w=3,
                bbox_h=4,
            )
        )

    response = client.delete(f"/api/v1/people/{created['person_id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Person is referenced by face or label data"


def test_people_delete_api_returns_409_when_person_is_referenced_by_face_label(
    tmp_path, monkeypatch
):
    database_url = _database_url(tmp_path, "people-delete-label-reference.db")
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    _get_session_factory.cache_clear()

    client = TestClient(app)
    created = client.post("/api/v1/people", json={"display_name": "Jane Doe"}).json()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-label-ref")
        connection.execute(
            insert(faces).values(
                face_id="face-label-ref",
                photo_id="photo-label-ref",
                person_id=None,
                bbox_x=1,
                bbox_y=2,
                bbox_w=3,
                bbox_h=4,
            )
        )
        connection.execute(
            insert(face_labels).values(
                face_label_id="face-label-1",
                face_id="face-label-ref",
                person_id=created["person_id"],
                label_source="human",
                confidence=None,
                model_version=None,
                provenance={"source": "test"},
            )
        )

    response = client.delete(f"/api/v1/people/{created['person_id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Person is referenced by face or label data"
```

- [ ] **Step 2: Run the delete tests and verify they fail**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -k "delete_api" -q
```

Expected: tests fail because `DELETE /api/v1/people/{person_id}` is not implemented.

- [ ] **Step 3: Add delete support and reference checks to the service**

Modify the SQLAlchemy import in `apps/api/app/services/people.py`:

```python
from sqlalchemy import delete, insert, select, update
```

Modify the storage import in `apps/api/app/services/people.py`:

```python
from app.storage import face_labels, faces, people
```

Add this exception class after `PersonNotFoundError`:

```python
class PersonInUseError(RuntimeError):
    pass
```

Append these functions to `apps/api/app/services/people.py`:

```python
def _person_has_references(connection: Connection, person_id: str) -> bool:
    face_reference = connection.execute(
        select(faces.c.face_id)
        .where(faces.c.person_id == person_id)
        .limit(1)
    ).first()
    if face_reference is not None:
        return True

    label_reference = connection.execute(
        select(face_labels.c.face_label_id)
        .where(face_labels.c.person_id == person_id)
        .limit(1)
    ).first()
    return label_reference is not None


def delete_person(
    connection: Connection,
    person_id: str,
) -> None:
    existing = get_person(connection, person_id)
    if existing is None:
        raise PersonNotFoundError("Person not found")

    if _person_has_references(connection, person_id):
        raise PersonInUseError("Person is referenced by face or label data")

    connection.execute(delete(people).where(people.c.person_id == person_id))
```

- [ ] **Step 4: Add the delete route**

Modify the FastAPI import in `apps/api/app/routers/people.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
```

Modify the service import in `apps/api/app/routers/people.py`:

```python
from app.services.people import (
    PersonInUseError,
    PersonNotFoundError,
    create_person,
    delete_person,
    get_person,
    list_people,
    update_person,
)
```

Append this route to `apps/api/app/routers/people.py`:

```python
@router.delete(
    "/{person_id}",
    summary="Delete person",
    description="Delete an unreferenced person record.",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Person not found"},
        status.HTTP_409_CONFLICT: {"description": "Person is referenced by face or label data"},
    },
)
def delete_person_route(
    person_id: str,
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_person(db.connection(), person_id)
    except PersonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PersonInUseError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Run the delete tests and full people API file**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -k "delete_api" -q
uv run python -m pytest apps/api/tests/test_people_api.py -q
```

Expected: delete slice passes, then the full `test_people_api.py` passes with `13 passed`.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add apps/api/app/routers/people.py apps/api/app/services/people.py apps/api/tests/test_people_api.py
git commit -m "feat(api): add safe people deletion"
```

### Task 4: Final Verification

**Files:**
- Verify: `apps/api/tests/test_people_api.py`
- Verify: `apps/api/tests/test_openapi_docs.py`
- Verify: `apps/api/tests`

- [ ] **Step 1: Run focused people API tests**

Run:

```bash
uv run python -m pytest apps/api/tests/test_people_api.py -q
```

Expected: all people API tests pass.

- [ ] **Step 2: Run OpenAPI documentation tests**

Run:

```bash
uv run python -m pytest apps/api/tests/test_openapi_docs.py -q
```

Expected: all OpenAPI docs tests pass.

- [ ] **Step 3: Run the full API test suite**

Run:

```bash
uv run python -m pytest apps/api/tests -q
```

Expected: the full API suite passes. If this uncovers an unrelated pre-existing failure, record the exact failing test and inspect whether the people API changes contributed to it before deciding whether to fix it in this branch.

- [ ] **Step 4: Inspect git status and commit any verification-only doc updates**

Run:

```bash
git status --short
```

Expected: only intentional code and test files are present, and they should already be committed by Tasks 1-3. Do not stage generated caches, `.venv`, or unrelated files.

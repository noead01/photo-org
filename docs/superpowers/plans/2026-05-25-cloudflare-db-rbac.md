# Cloudflare DB RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add database-backed global RBAC for Cloudflare-authenticated users, auto-provision user records on first access, and move album ownership plus protected endpoint authorization onto app user identities.

**Architecture:** Introduce a durable `users` principal table and a `user_role_assignments` table, then resolve Cloudflare-authenticated requests to an app user before route authorization runs. Keep the first cut narrow by leaving existing album ownership columns structurally unchanged while changing their meaning for new writes from caller-provided strings to app `user_id` values.

**Tech Stack:** FastAPI, SQLAlchemy Core, Alembic, pytest, SQLite test databases, PostgreSQL-compatible schema definitions

---

## File Structure

- Create: `apps/api/alembic/versions/20260525_000001_add_users_and_rbac_tables.py`
  Purpose: add `users` and `user_role_assignments`, plus constraints and indexes needed for global RBAC.
- Create: `apps/api/tests/test_auth_rbac.py`
  Purpose: focused request-resolution and role-enforcement tests for auto-provisioning and DB-backed authorization.
- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
  Purpose: declare `users` and `user_role_assignments` in the code-owned schema.
- Modify: `apps/api/app/auth.py`
  Purpose: resolve Cloudflare identity into a durable app user and load DB roles.
- Modify: `apps/api/app/dependencies.py`
  Purpose: replace header-trust authorization with user and role dependencies backed by the DB.
- Modify: `apps/api/app/routers/albums.py`
  Purpose: scope album ownership and attribution by app `user_id`.
- Modify: `apps/api/app/routers/face_assignments.py`
  Purpose: keep face-labeling writes on contributor/admin DB roles.
- Modify: `apps/api/app/routers/suggestions.py`
  Purpose: keep suggestion confirmation writes on contributor/admin DB roles.
- Modify: `apps/api/tests/test_albums_and_exports_api.py`
  Purpose: verify album ownership uses DB identities and resource scoping remains correct.
- Modify: `apps/api/tests/test_face_assignment_api.py`
  Purpose: verify contributor/admin role enforcement uses DB role assignments.
- Modify: `apps/api/tests/test_main.py`
  Purpose: keep auth-mode and CORS-level tests aligned with the new dependencies if needed.
- Modify: `compose.yaml`
  Purpose: continue passing auth-mode env vars through the runtime container.
- Modify: `.env.compose.example`
  Purpose: document runtime env vars needed for Cloudflare-backed auth mode.

### Task 1: Add RBAC Schema And Migration

**Files:**
- Create: `apps/api/alembic/versions/20260525_000001_add_users_and_rbac_tables.py`
- Modify: `packages/db-schema/photoorg_db_schema/schema.py`
- Test: `apps/api/tests/test_albums_and_exports_api.py`

- [ ] **Step 1: Write the failing schema test expectations**

Add the new table/column assertions near the existing album schema assertions in `apps/api/tests/test_albums_and_exports_api.py`:

```python
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    role_columns = {column["name"] for column in inspector.get_columns("user_role_assignments")}

    assert {
        "user_id",
        "auth_provider",
        "auth_subject",
        "email",
        "display_name",
        "created_ts",
        "updated_ts",
    } <= user_columns
    assert {"user_id", "role", "created_ts", "updated_ts"} <= role_columns
```

- [ ] **Step 2: Run the schema test to verify it fails**

Run:

```bash
uv run python -m pytest apps/api/tests/test_albums_and_exports_api.py -k schema -q
```

Expected: FAIL because `users` and `user_role_assignments` do not exist.

- [ ] **Step 3: Add the schema definitions**

Update `packages/db-schema/photoorg_db_schema/schema.py` with:

```python
users = Table(
    "users",
    metadata,
    Column("user_id", String(36), primary_key=True),
    Column("auth_provider", String, nullable=False),
    Column("auth_subject", String, nullable=False, unique=True),
    Column("email", String, nullable=False, unique=True),
    Column("display_name", String),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
)

user_role_assignments = Table(
    "user_role_assignments",
    metadata,
    Column("user_id", String(36), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
    Column("role", String, primary_key=True),
    Column("created_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    Column("updated_ts", TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    CheckConstraint("role IN ('viewer', 'contributor', 'admin')", name="ck_user_role_assignments_role"),
)

Index("idx_users_email", users.c.email)
Index("idx_user_role_assignments_role", user_role_assignments.c.role)
```

- [ ] **Step 4: Add the Alembic migration**

Create `apps/api/alembic/versions/20260525_000001_add_users_and_rbac_tables.py`:

```python
"""add users and rbac tables

Revision ID: 20260525_000001
Revises: 20260508_000001
Create Date: 2026-05-25 00:00:01
"""

from alembic import op
import sqlalchemy as sa

revision = "20260525_000001"
down_revision = "20260508_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("auth_provider", sa.String(), nullable=False),
        sa.Column("auth_subject", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("idx_users_email", "users", ["email"])

    op.create_table(
        "user_role_assignments",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(), primary_key=True),
        sa.Column("created_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_ts", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("role IN ('viewer', 'contributor', 'admin')", name="ck_user_role_assignments_role"),
    )
    op.create_index("idx_user_role_assignments_role", "user_role_assignments", ["role"])


def downgrade() -> None:
    op.drop_index("idx_user_role_assignments_role", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")
```

- [ ] **Step 5: Run the schema test to verify it passes**

Run:

```bash
uv run python -m pytest apps/api/tests/test_albums_and_exports_api.py -k schema -q
```

Expected: PASS with the new tables present.

- [ ] **Step 6: Commit the schema slice**

```bash
git add packages/db-schema/photoorg_db_schema/schema.py apps/api/alembic/versions/20260525_000001_add_users_and_rbac_tables.py apps/api/tests/test_albums_and_exports_api.py
git commit -m "feat: add database-backed user and role tables"
```

### Task 2: Resolve Cloudflare Identity To A DB User

**Files:**
- Modify: `apps/api/app/auth.py`
- Modify: `apps/api/app/dependencies.py`
- Create: `apps/api/tests/test_auth_rbac.py`

- [ ] **Step 1: Write the failing user auto-provisioning test**

Create `apps/api/tests/test_auth_rbac.py` with:

```python
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select

from app.dependencies import _get_session_factory
from app.main import app
from app.migrations import upgrade_database
from app.storage import users


def test_cloudflare_access_auto_provisions_user_without_roles(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    client = TestClient(app)
    response = client.get(
        "/api/v1/albums",
        headers={"Cf-Access-Authenticated-User-Email": "new.user@example.com"},
    )

    assert response.status_code == 200
    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        persisted = connection.execute(
            select(users.c.email, users.c.auth_provider)
        ).mappings().all()
    assert persisted == [{"email": "new.user@example.com", "auth_provider": "cloudflare_access"}]
```

- [ ] **Step 2: Run the auth test to verify it fails**

Run:

```bash
uv run python -m pytest apps/api/tests/test_auth_rbac.py -q
```

Expected: FAIL because the app does not yet create or load DB users.

- [ ] **Step 3: Implement DB-backed identity resolution**

Update `apps/api/app/auth.py` to add a resolved app-user model plus lookup/create helpers:

```python
@dataclass(frozen=True)
class AppUser:
    user_id: str
    email: str
    display_name: str | None
    roles: frozenset[str]


def get_or_create_cloudflare_user(db: Session, *, email: str, subject: str | None = None) -> AppUser:
    normalized_email = _normalize_email(email)
    auth_subject = (subject or normalized_email or "").strip().lower()
    row = db.execute(
        select(users).where(users.c.auth_subject == auth_subject)
    ).mappings().one_or_none()
    if row is None:
        now = datetime.now(tz=UTC)
        user_id = str(uuid4())
        db.execute(
            insert(users).values(
                user_id=user_id,
                auth_provider="cloudflare_access",
                auth_subject=auth_subject,
                email=normalized_email,
                display_name=None,
                created_ts=now,
                updated_ts=now,
            )
        )
        db.commit()
        row = db.execute(
            select(users).where(users.c.user_id == user_id)
        ).mappings().one()
    assigned_roles = frozenset(
        db.execute(
            select(user_role_assignments.c.role).where(user_role_assignments.c.user_id == row["user_id"])
        ).scalars().all()
    )
    return AppUser(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        roles=assigned_roles,
    )
```

- [ ] **Step 4: Replace the simple string dependency with app-user resolution**

Update `apps/api/app/dependencies.py` to expose:

```python
def require_authenticated_user(
    db: Session = Depends(get_db),
    cloudflare_access_email: str | None = Header(default=None, alias=CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER),
) -> AppUser:
    if get_auth_mode() == AUTH_MODE_CLOUDFLARE_ACCESS:
        resolved_identity = resolve_cloudflare_access_user(cloudflare_access_email)
        return get_or_create_cloudflare_user(db, email=resolved_identity.email)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Legacy auth mode not supported in this plan.")
```

Then keep a compatibility wrapper:

```python
def require_authenticated_user_id(user: AppUser = Depends(require_authenticated_user)) -> str:
    return user.user_id
```

- [ ] **Step 5: Run the auth test to verify it passes**

Run:

```bash
uv run python -m pytest apps/api/tests/test_auth_rbac.py -q
```

Expected: PASS with a persisted `users` row.

- [ ] **Step 6: Commit the identity-resolution slice**

```bash
git add apps/api/app/auth.py apps/api/app/dependencies.py apps/api/tests/test_auth_rbac.py
git commit -m "feat: resolve Cloudflare requests to app users"
```

### Task 3: Enforce DB Roles On Protected Endpoints

**Files:**
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/routers/face_assignments.py`
- Modify: `apps/api/app/routers/suggestions.py`
- Modify: `apps/api/tests/test_face_assignment_api.py`
- Modify: `apps/api/tests/test_auth_rbac.py`

- [ ] **Step 1: Write the failing contributor-role test**

Add to `apps/api/tests/test_auth_rbac.py`:

```python
def test_cloudflare_access_user_without_role_cannot_confirm_face(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'auth-rbac-face.db'}"
    upgrade_database(database_url)
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    _get_session_factory.cache_clear()

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        _insert_photo(connection, photo_id="photo-1")
        _insert_person(connection, person_id="person-1", display_name="Jane Doe")
        connection.execute(insert(faces).values(face_id="face-1", photo_id="photo-1", person_id=None))

    client = TestClient(app)
    response = client.post(
        "/api/v1/faces/face-1/assignments",
        json={"person_id": "person-1"},
        headers={"Cf-Access-Authenticated-User-Email": "viewer@example.com"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Face validation role required"}
```

- [ ] **Step 2: Run the face auth tests to verify they fail correctly**

Run:

```bash
uv run python -m pytest apps/api/tests/test_auth_rbac.py apps/api/tests/test_face_assignment_api.py -k "cloudflare_access or role" -q
```

Expected: FAIL because DB role assignments are not yet consulted.

- [ ] **Step 3: Implement DB role lookup and contributor/admin enforcement**

Update `apps/api/app/dependencies.py`:

```python
ROLE_RANK = {
    "viewer": 1,
    "contributor": 2,
    "admin": 3,
}


def require_role(required_role: str):
    def dependency(user: AppUser = Depends(require_authenticated_user)) -> AppUser:
        user_rank = max((ROLE_RANK[role] for role in user.roles), default=0)
        required_rank = ROLE_RANK[required_role]
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face validation role required" if required_role == "contributor" else "Admin role required",
            )
        return user

    return dependency


def require_face_validation_role(_: AppUser = Depends(require_role("contributor"))) -> str:
    return "contributor"
```

- [ ] **Step 4: Keep protected routers on the DB-backed dependency**

Ensure `apps/api/app/routers/face_assignments.py` and `apps/api/app/routers/suggestions.py` still depend on `require_face_validation_role` and do not reintroduce header-based auth.

- [ ] **Step 5: Run the face auth tests to verify they pass**

Run:

```bash
uv run python -m pytest apps/api/tests/test_auth_rbac.py apps/api/tests/test_face_assignment_api.py -k "cloudflare_access or role" -q
```

Expected: PASS, including no-role denial and contributor access.

- [ ] **Step 6: Commit the authorization slice**

```bash
git add apps/api/app/dependencies.py apps/api/app/routers/face_assignments.py apps/api/app/routers/suggestions.py apps/api/tests/test_auth_rbac.py apps/api/tests/test_face_assignment_api.py
git commit -m "feat: enforce db-backed roles on protected endpoints"
```

### Task 4: Move Album Ownership To App User IDs

**Files:**
- Modify: `apps/api/app/routers/albums.py`
- Modify: `apps/api/tests/test_albums_and_exports_api.py`
- Modify: `apps/api/tests/test_search_service.py`

- [ ] **Step 1: Write the failing ownership test**

Extend `apps/api/tests/test_albums_and_exports_api.py`:

```python
    engine = create_engine(f"sqlite:///{tmp_path / 'albums-cloudflare.db'}", future=True)
    with engine.connect() as connection:
        owner_row = connection.execute(
            select(users.c.user_id, users.c.email).where(users.c.email == "owner@example.com")
        ).mappings().one()
        album_row = connection.execute(
            select(albums.c.owner_user_id).where(albums.c.album_id == album_id)
        ).mappings().one()
    assert album_row["owner_user_id"] == owner_row["user_id"]
```

- [ ] **Step 2: Run the album tests to verify they fail**

Run:

```bash
uv run python -m pytest apps/api/tests/test_albums_and_exports_api.py -k cloudflare_access_scope_by_authenticated_email -q
```

Expected: FAIL because album ownership is still compared against email, not app `user_id`.

- [ ] **Step 3: Update album endpoints to consume the resolved app user**

In `apps/api/app/routers/albums.py`, replace plain `user_id` dependencies with the full app user where needed:

```python
from app.auth import AppUser
from app.dependencies import require_authenticated_user


def create_album_endpoint(
    body: CreateAlbumRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_authenticated_user),
) -> AlbumResponse:
    if _album_name_exists(db, owner_user_id=user.user_id, name=body.name):
        ...
    db.execute(
        insert(albums).values(
            album_id=album_id,
            name=body.name,
            owner_user_id=user.user_id,
            kind=body.kind,
            created_ts=now,
            updated_ts=now,
        )
    )
```

Also update list/detail/update/delete/item-membership paths to scope by `user.user_id`, and write `editable_album_items.added_by_user_id=user.user_id`.

- [ ] **Step 4: Update search-service tests that currently assume `demo-user`**

Adjust `apps/api/tests/test_search_service.py` fixtures and expectations from `"demo-user"` to explicit app user ids such as `"user-1"` so they no longer depend on the old fallback identity semantics.

- [ ] **Step 5: Run the album and search tests to verify they pass**

Run:

```bash
uv run python -m pytest apps/api/tests/test_albums_and_exports_api.py apps/api/tests/test_search_service.py -k "album or owner_user_id or added_by_user_id" -q
```

Expected: PASS with ownership stored as app `user_id`.

- [ ] **Step 6: Commit the ownership slice**

```bash
git add apps/api/app/routers/albums.py apps/api/tests/test_albums_and_exports_api.py apps/api/tests/test_search_service.py
git commit -m "feat: store album ownership by app user id"
```

### Task 5: Final Verification And Runtime Wiring

**Files:**
- Modify: `compose.yaml`
- Modify: `.env.compose.example`
- Test: `apps/api/tests/test_main.py`

- [ ] **Step 1: Write or adjust the runtime configuration expectations**

Add any needed assertions in `apps/api/tests/test_main.py` for the auth mode boundary, but keep the scope limited to config and dependency behavior rather than full RBAC integration.

- [ ] **Step 2: Keep the runtime env vars documented and passed through**

Ensure `compose.yaml` and `.env.compose.example` contain:

```yaml
PHOTO_ORG_AUTH_MODE: ${PHOTO_ORG_AUTH_MODE:-legacy_headers}
PHOTO_ORG_AUTH_CONTRIBUTOR_EMAILS: ${PHOTO_ORG_AUTH_CONTRIBUTOR_EMAILS:-}
PHOTO_ORG_AUTH_ADMIN_EMAILS: ${PHOTO_ORG_AUTH_ADMIN_EMAILS:-}
```

Note: these contributor/admin env vars should remain only if they are still needed during the transition. If the DB-backed implementation no longer depends on them, remove them here and in tests instead of carrying dead configuration.

- [ ] **Step 3: Run the final impacted API test suite**

Run:

```bash
uv run python -m pytest apps/api/tests/test_auth_rbac.py apps/api/tests/test_albums_and_exports_api.py apps/api/tests/test_face_assignment_api.py apps/api/tests/test_face_suggestion_review_api.py apps/api/tests/test_main.py -q
```

Expected: PASS with all impacted RBAC and route tests green.

- [ ] **Step 4: Run the migration-focused verification**

Run:

```bash
uv run python -m pytest apps/api/tests/test_migrations.py apps/api/tests/test_schema_definition.py -q
```

Expected: PASS with the new tables included in the schema and migration chain.

- [ ] **Step 5: Commit the runtime and verification slice**

```bash
git add compose.yaml .env.compose.example apps/api/tests/test_main.py
git commit -m "chore: wire runtime config for db-backed rbac"
```

## Self-Review

- Spec coverage:
  - DB identity abstraction: covered by Tasks 1 and 2.
  - DB-backed global roles: covered by Tasks 1 and 3.
  - Protected endpoint authorization: covered by Task 3.
  - Ownership by app principal: covered by Task 4.
  - Transitional runtime configuration and verification: covered by Task 5.
- Placeholder scan:
  - No `TODO`, `TBD`, or “similar to previous task” shortcuts remain.
- Type consistency:
  - The plan consistently uses `AppUser`, `users`, `user_role_assignments`, `owner_user_id`, and `added_by_user_id`.

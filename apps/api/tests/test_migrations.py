import importlib.util
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, func, inspect, select

from app.db.queue import IngestQueueStore
from app.processing.ingest import ingest_directory
from app.storage import photos


SAMPLES_DIR = Path("/mnt/d/Projects/photo-org/apps/api/features/samples")


class NoOpTriggerClient:
    def __init__(self) -> None:
        self.calls = 0

    def process_pending_queue(self) -> None:
        self.calls += 1


def test_upgrade_database_creates_schema(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    upgrade_database(database_url)

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        tables = set(inspect(connection).get_table_names())

    assert {"photos", "faces", "photo_tags", "people", "face_labels"} <= tables


def test_upgrade_database_creates_ingest_queue_table(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'queue.db'}"

    upgrade_database(database_url)

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        inspector = inspect(connection)

        tables = set(inspector.get_table_names())
        unique_constraints = inspector.get_unique_constraints("ingest_queue")
        columns = {column["name"]: column for column in inspector.get_columns("ingest_queue")}
        indexes = inspector.get_indexes("ingest_queue")

    assert "ingest_queue" in tables
    assert any(constraint["column_names"] == ["idempotency_key"] for constraint in unique_constraints)
    assert columns["status"]["default"] == "'pending'"
    assert columns["attempt_count"]["default"] == "0"
    assert any(
        index["name"] == "idx_ingest_queue_status_enqueued_ts"
        and index["column_names"] == ["status", "enqueued_ts"]
        for index in indexes
    )


def test_initial_postgresql_migration_does_not_create_vector_extension(monkeypatch):
    revision_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20260321_000001_initial_schema.py"
    spec = importlib.util.spec_from_file_location("initial_schema_revision", revision_path)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    recorded_sql: list[str] = []

    monkeypatch.setattr(
        migration.op,
        "get_bind",
        lambda: SimpleNamespace(dialect=SimpleNamespace(name="postgresql")),
    )
    monkeypatch.setattr(
        migration.op,
        "execute",
        lambda sql: recorded_sql.append(str(sql)),
    )
    monkeypatch.setattr(migration.op, "create_table", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)

    migration.upgrade()

    assert recorded_sql == []


def test_ingest_requires_existing_schema(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'missing-schema.db'}"
    trigger_client = NoOpTriggerClient()

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=database_url,
        trigger_client=trigger_client,
    )

    assert result.errors
    assert "no such table: ingest_queue" in result.errors[0]
    assert trigger_client.calls == 0


def test_ingest_succeeds_after_running_migrations(tmp_path):
    from app.migrations import upgrade_database

    database_url = f"sqlite:///{tmp_path / 'ingest.db'}"
    upgrade_database(database_url)
    trigger_client = NoOpTriggerClient()

    result = ingest_directory(
        SAMPLES_DIR,
        database_url=database_url,
        trigger_client=trigger_client,
    )

    assert result.errors == []
    assert result.enqueued == 10
    assert trigger_client.calls == 1

    queue_store = IngestQueueStore(database_url)
    pending_rows = queue_store.list_pending()

    assert len(pending_rows) == 10

    engine = create_engine(database_url, future=True)
    with engine.connect() as connection:
        count = connection.execute(select(func.count()).select_from(photos)).scalar_one()

    assert count == 0

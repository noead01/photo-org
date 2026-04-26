from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.engine import Connection

from app.db.session import create_session_factory, dispose_session_factory
from photoorg_db_schema import ingest_run_files, ingest_runs


@dataclass(frozen=True)
class IngestRunFileOutcome:
    ingest_queue_id: str
    path: str
    outcome: str
    error_detail: str | None = None


class IngestRunStore:
    def __init__(self, database_url: str | Path | None = None) -> None:
        self._session_factory = create_session_factory(database_url)

    def close(self) -> None:
        dispose_session_factory(self._session_factory)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def create_run(
        self,
        *,
        watched_folder_id: str | None = None,
        connection: Connection | None = None,
    ) -> str:
        ingest_run_id = str(uuid4())
        values = {
            "ingest_run_id": ingest_run_id,
            "watched_folder_id": watched_folder_id,
            "status": "processing",
        }
        if connection is not None:
            connection.execute(ingest_runs.insert().values(**values))
            return ingest_run_id

        with self._session_factory() as session:
            session.execute(ingest_runs.insert().values(**values))
            session.commit()
        return ingest_run_id

    def append_file_outcome(
        self,
        ingest_run_id: str,
        outcome: IngestRunFileOutcome,
        *,
        connection: Connection | None = None,
    ) -> None:
        values = {
            "ingest_run_file_id": str(uuid4()),
            "ingest_run_id": ingest_run_id,
            "ingest_queue_id": outcome.ingest_queue_id,
            "path": outcome.path,
            "outcome": outcome.outcome,
            "error_detail": outcome.error_detail,
        }
        if connection is not None:
            connection.execute(ingest_run_files.insert().values(**values))
            return

        with self._session_factory() as session:
            session.execute(ingest_run_files.insert().values(**values))
            session.commit()

    def finalize_run(
        self,
        ingest_run_id: str,
        *,
        status: str,
        files_seen: int,
        files_created: int,
        files_updated: int,
        error_count: int,
        error_summary: str | None,
        connection: Connection | None = None,
    ) -> None:
        statement = (
            update(ingest_runs)
            .where(ingest_runs.c.ingest_run_id == ingest_run_id)
            .values(
                status=status,
                completed_ts=datetime.now(tz=UTC),
                files_seen=files_seen,
                files_created=files_created,
                files_updated=files_updated,
                error_count=error_count,
                error_summary=error_summary,
            )
        )
        if connection is not None:
            result = connection.execute(statement)
            if not result.rowcount:
                raise LookupError(f"missing ingest run: {ingest_run_id}")
            return

        with self._session_factory() as session:
            result = session.execute(statement)
            if not result.rowcount:
                session.rollback()
                raise LookupError(f"missing ingest run: {ingest_run_id}")
            session.commit()

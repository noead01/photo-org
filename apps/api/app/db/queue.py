from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from app.db.session import create_session_factory
from photoorg_db_schema import ingest_queue

PROCESSING_LEASE_SECONDS = 300


@dataclass(frozen=True)
class QueueRow:
    ingest_queue_id: str
    payload_type: str
    payload_json: dict
    idempotency_key: str
    status: str
    attempt_count: int
    enqueued_ts: datetime
    last_attempt_ts: datetime | None
    processed_ts: datetime | None
    last_error: str | None


@dataclass(frozen=True)
class EnqueueResult:
    ingest_queue_id: str
    created: bool


class IngestQueueStore:
    def __init__(self, database_url: str | Path | None = None) -> None:
        self._session_factory = create_session_factory(database_url)

    def enqueue(self, *, payload_type: str, payload: dict, idempotency_key: str) -> str:
        queue_id = str(uuid4())

        with self._session_factory() as session:
            try:
                session.execute(
                    ingest_queue.insert().values(
                        ingest_queue_id=queue_id,
                        payload_type=payload_type,
                        payload_json=payload,
                        idempotency_key=idempotency_key,
                    )
                )
                session.commit()
                return queue_id
            except IntegrityError as exc:
                session.rollback()
                if not _is_duplicate_idempotency_key_error(exc):
                    raise exc
                existing_id = session.execute(
                    select(ingest_queue.c.ingest_queue_id).where(
                        ingest_queue.c.idempotency_key == idempotency_key
                    )
                ).scalar_one_or_none()
                if existing_id is None:
                    raise exc
                return existing_id

    def enqueue_in_transaction(
        self,
        *,
        payload_type: str,
        payload: dict,
        idempotency_key: str,
        connection: Connection,
    ) -> EnqueueResult:
        queue_id = str(uuid4())
        values = {
            "ingest_queue_id": queue_id,
            "payload_type": payload_type,
            "payload_json": payload,
            "idempotency_key": idempotency_key,
        }
        dialect_name = connection.dialect.name

        if dialect_name == "sqlite":
            inserted_id = connection.execute(
                sqlite_insert(ingest_queue)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[ingest_queue.c.idempotency_key])
                .returning(ingest_queue.c.ingest_queue_id)
            ).scalar_one_or_none()
        elif dialect_name == "postgresql":
            inserted_id = connection.execute(
                postgresql_insert(ingest_queue)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[ingest_queue.c.idempotency_key])
                .returning(ingest_queue.c.ingest_queue_id)
            ).scalar_one_or_none()
        else:
            inserted_id = _enqueue_with_integrity_fallback(connection=connection, values=values)

        if inserted_id is not None:
            return EnqueueResult(ingest_queue_id=inserted_id, created=True)

        existing_id = connection.execute(
            select(ingest_queue.c.ingest_queue_id).where(
                ingest_queue.c.idempotency_key == idempotency_key
            )
        ).scalar_one_or_none()
        if existing_id is None:
            raise RuntimeError(
                f"queue row lookup failed for idempotency key {idempotency_key}"
            )
        return EnqueueResult(ingest_queue_id=existing_id, created=False)

    def list_pending(self) -> list[QueueRow]:
        return self.list_by_status("pending")

    def list_processable(self, *, limit: int) -> list[QueueRow]:
        reclaim_before = _processing_lease_cutoff()
        with self._session_factory() as session:
            rows = session.execute(
                select(ingest_queue)
                .where(
                    (ingest_queue.c.status == "pending")
                    | (
                        (ingest_queue.c.status == "processing")
                        & ingest_queue.c.last_attempt_ts.is_not(None)
                        & (ingest_queue.c.last_attempt_ts <= reclaim_before)
                    )
                )
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
                .limit(limit)
            ).mappings()
            return [QueueRow(**row) for row in rows]

    def list_by_status(self, status: str) -> list[QueueRow]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ingest_queue)
                .where(ingest_queue.c.status == status)
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
            ).mappings()
            return [QueueRow(**row) for row in rows]

    def claim_pending(self, *, limit: int) -> list[QueueRow]:
        # Legacy compatibility surface; Task 3 processing uses lease-aware list_processable().
        return self.list_processable(limit=limit)

    def begin_processing_attempt(
        self,
        ingest_queue_id: str,
        *,
        connection: Connection,
    ) -> QueueRow | None:
        now = datetime.now(tz=UTC)
        reclaim_before = _processing_lease_cutoff(now)
        result = connection.execute(
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
            .where(
                (ingest_queue.c.status == "pending")
                | (
                    (ingest_queue.c.status == "processing")
                    & ingest_queue.c.last_attempt_ts.is_not(None)
                    & (ingest_queue.c.last_attempt_ts <= reclaim_before)
                )
            )
            .values(
                status="processing",
                attempt_count=ingest_queue.c.attempt_count + 1,
                last_attempt_ts=now,
                last_error=None,
            )
        )
        if not result.rowcount:
            return None

        row = connection.execute(
            select(ingest_queue).where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
        ).mappings().one()
        return QueueRow(**row)

    def mark_completed(
        self,
        ingest_queue_id: str,
        last_error: str | None = None,
        *,
        connection: Connection | None = None,
    ) -> None:
        statement = (
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
            .where(ingest_queue.c.status == "processing")
            .values(
                status="completed",
                processed_ts=datetime.now(tz=UTC),
                last_error=last_error,
            )
        )
        if connection is not None:
            connection.execute(statement)
            return

        with self._session_factory() as session:
            session.execute(statement)
            session.commit()

    def mark_failed(
        self,
        ingest_queue_id: str,
        error_message: str,
        *,
        connection: Connection | None = None,
    ) -> None:
        statement = (
            update(ingest_queue)
            .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
            .where(ingest_queue.c.status.in_(("pending", "processing")))
            .values(
                status="failed",
                processed_ts=None,
                last_error=error_message,
            )
        )
        if connection is not None:
            connection.execute(statement)
            return

        with self._session_factory() as session:
            session.execute(statement)
            session.commit()

    def record_retryable_failure(self, ingest_queue_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            session.execute(
                update(ingest_queue)
                .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
                .where(ingest_queue.c.status.in_(("pending", "processing")))
                .values(
                    status="processing",
                    attempt_count=ingest_queue.c.attempt_count + 1,
                    last_attempt_ts=datetime.now(tz=UTC),
                    processed_ts=None,
                    last_error=error_message,
                )
            )
            session.commit()

    def record_permanent_failure(self, ingest_queue_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            session.execute(
                update(ingest_queue)
                .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
                .where(ingest_queue.c.status.in_(("pending", "processing")))
                .values(
                    status="failed",
                    attempt_count=ingest_queue.c.attempt_count + 1,
                    last_attempt_ts=datetime.now(tz=UTC),
                    processed_ts=None,
                    last_error=error_message,
                )
            )
            session.commit()


def _is_duplicate_idempotency_key_error(exc: IntegrityError) -> bool:
    message = str(exc.orig).lower()
    return "idempotency_key" in message and (
        "unique constraint failed" in message
        or "duplicate key value violates unique constraint" in message
    )


def _enqueue_with_integrity_fallback(
    *,
    connection: Connection,
    values: dict[str, object],
) -> str | None:
    nested = connection.begin_nested()
    try:
        connection.execute(ingest_queue.insert().values(**values))
    except IntegrityError as exc:
        nested.rollback()
        if not _is_duplicate_idempotency_key_error(exc):
            raise exc
        return None

    nested.commit()
    return str(values["ingest_queue_id"])


def _processing_lease_cutoff(now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(tz=UTC)
    return now - timedelta(seconds=PROCESSING_LEASE_SECONDS)

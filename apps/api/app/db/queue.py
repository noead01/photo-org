from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.db.session import create_session_factory
from photoorg_db_schema import ingest_queue


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

    def list_pending(self) -> list[QueueRow]:
        return self.list_by_status("pending")

    def list_by_status(self, status: str) -> list[QueueRow]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ingest_queue)
                .where(ingest_queue.c.status == status)
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
            ).mappings()
            return [QueueRow(**row) for row in rows]

    def claim_pending(self, *, limit: int) -> list[QueueRow]:
        now = datetime.now(tz=UTC)

        with self._session_factory() as session:
            rows = session.execute(
                select(ingest_queue)
                .where(ingest_queue.c.status == "pending")
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
                .limit(limit)
            ).mappings()

            claimed_ids: list[str] = []
            for row in rows:
                result = session.execute(
                    update(ingest_queue)
                    .where(ingest_queue.c.ingest_queue_id == row["ingest_queue_id"])
                    .where(ingest_queue.c.status == "pending")
                    .values(
                        status="processing",
                        attempt_count=ingest_queue.c.attempt_count + 1,
                        last_attempt_ts=now,
                        last_error=None,
                    )
                )
                if result.rowcount:
                    claimed_ids.append(row["ingest_queue_id"])

            session.commit()

            if not claimed_ids:
                return []

            claimed_rows = session.execute(
                select(ingest_queue)
                .where(ingest_queue.c.ingest_queue_id.in_(claimed_ids))
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
            ).mappings()
            return [QueueRow(**row) for row in claimed_rows]

    def mark_completed(self, ingest_queue_id: str) -> None:
        with self._session_factory() as session:
            session.execute(
                update(ingest_queue)
                .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
                .values(
                    status="completed",
                    processed_ts=datetime.now(tz=UTC),
                    last_error=None,
                )
            )
            session.commit()

    def mark_failed(self, ingest_queue_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            session.execute(
                update(ingest_queue)
                .where(ingest_queue.c.ingest_queue_id == ingest_queue_id)
                .values(
                    status="failed",
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

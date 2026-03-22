from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
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
            except IntegrityError:
                session.rollback()
                existing_id = session.execute(
                    select(ingest_queue.c.ingest_queue_id).where(
                        ingest_queue.c.idempotency_key == idempotency_key
                    )
                ).scalar_one()
                return existing_id

    def list_pending(self) -> list[QueueRow]:
        with self._session_factory() as session:
            rows = session.execute(
                select(ingest_queue)
                .where(ingest_queue.c.status == "pending")
                .order_by(ingest_queue.c.enqueued_ts, ingest_queue.c.ingest_queue_id)
            ).mappings()
            return [QueueRow(**row) for row in rows]

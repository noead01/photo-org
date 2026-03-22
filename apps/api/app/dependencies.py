import os
from functools import lru_cache
from typing import Iterator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import create_session_factory


WORKER_ROLE_HEADER = "X-Worker-Role"
INGEST_PROCESSOR_ROLE = "ingest-processor"


@lru_cache(maxsize=None)
def _get_session_factory(database_url: str | None):
    return create_session_factory(database_url)


def get_db() -> Iterator[Session]:
    db = _get_session_factory(os.getenv("DATABASE_URL"))()
    try:
        yield db
    finally:
        db.close()


def require_worker_role(
    worker_role: str | None = Header(default=None, alias=WORKER_ROLE_HEADER),
) -> None:
    if worker_role != INGEST_PROCESSOR_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker role required",
        )

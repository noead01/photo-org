import os
from typing import Iterator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import create_session_factory


WORKER_ROLE_HEADER = "X-Worker-Role"
INGEST_PROCESSOR_ROLE = "ingest-processor"


def get_db() -> Iterator[Session]:
    session_local = create_session_factory(os.getenv("DATABASE_URL"))
    db = session_local()
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

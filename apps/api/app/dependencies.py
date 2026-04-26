import os
from functools import lru_cache
from typing import Iterator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import create_session_factory


WORKER_ROLE_HEADER = "X-Worker-Role"
INGEST_PROCESSOR_ROLE = "ingest-processor"
FACE_VALIDATION_ROLE_HEADER = "X-Face-Validation-Role"
FACE_VALIDATION_ROLE_CONTRIBUTOR = "contributor"
FACE_VALIDATION_ROLE_ADMIN = "admin"
FACE_VALIDATION_ROLES = frozenset(
    {
        FACE_VALIDATION_ROLE_CONTRIBUTOR,
        FACE_VALIDATION_ROLE_ADMIN,
    }
)


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


def require_face_validation_role(
    face_validation_role: str | None = Header(default=None, alias=FACE_VALIDATION_ROLE_HEADER),
) -> str:
    if face_validation_role not in FACE_VALIDATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Face validation role required",
        )
    return face_validation_role

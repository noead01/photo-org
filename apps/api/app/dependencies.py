import os
from functools import lru_cache
from typing import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    AUTH_MODE_CLOUDFLARE_ACCESS,
    CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER,
    AppUser,
    get_or_create_cloudflare_user,
    resolve_cloudflare_access_identity,
)
from app.db.session import create_session_factory


AUTH_MODE_ENV = "PHOTO_ORG_AUTH_MODE"
AUTH_MODE_LEGACY_HEADERS = "legacy_headers"
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
USER_ID_HEADER = "X-Photo-Org-User-Id"
ROLE_RANK = {
    "viewer": 1,
    "contributor": 2,
    "admin": 3,
}


@lru_cache(maxsize=None)
def _get_session_factory(database_url: str | None):
    return create_session_factory(database_url)


def get_db() -> Iterator[Session]:
    db = _get_session_factory(os.getenv("DATABASE_URL"))()
    try:
        yield db
    finally:
        db.close()


def get_auth_mode() -> str:
    raw_mode = (os.getenv(AUTH_MODE_ENV) or AUTH_MODE_LEGACY_HEADERS).strip().lower()
    if raw_mode in {AUTH_MODE_LEGACY_HEADERS, AUTH_MODE_CLOUDFLARE_ACCESS}:
        return raw_mode
    return AUTH_MODE_LEGACY_HEADERS


def require_worker_role(
    worker_role: str | None = Header(default=None, alias=WORKER_ROLE_HEADER),
) -> None:
    if worker_role != INGEST_PROCESSOR_ROLE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker role required",
        )


def require_role(required_role: str):
    def dependency(user: AppUser = Depends(require_authenticated_user)) -> AppUser:
        user_rank = max((ROLE_RANK.get(role, 0) for role in user.roles), default=0)
        required_rank = ROLE_RANK[required_role]
        if user_rank < required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face validation role required"
                if required_role == "contributor"
                else "Admin role required",
            )
        return user

    return dependency


def require_face_validation_role(
    face_validation_role: str | None = Header(default=None, alias=FACE_VALIDATION_ROLE_HEADER),
    db: Session = Depends(get_db),
    cloudflare_access_email: str | None = Header(
        default=None, alias=CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER
    ),
) -> str:
    if get_auth_mode() == AUTH_MODE_CLOUDFLARE_ACCESS:
        resolved_identity = resolve_cloudflare_access_identity(cloudflare_access_email)
        user = get_or_create_cloudflare_user(db, email=resolved_identity.email)
        user_rank = max((ROLE_RANK.get(role, 0) for role in user.roles), default=0)
        if user_rank < ROLE_RANK["contributor"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Face validation role required",
            )
        return FACE_VALIDATION_ROLE_CONTRIBUTOR

    if face_validation_role not in FACE_VALIDATION_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Face validation role required",
        )
    return face_validation_role


def require_authenticated_user(
    db: Session = Depends(get_db),
    cloudflare_access_email: str | None = Header(
        default=None, alias=CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER
    ),
) -> AppUser:
    if get_auth_mode() == AUTH_MODE_CLOUDFLARE_ACCESS:
        resolved_identity = resolve_cloudflare_access_identity(cloudflare_access_email)
        return get_or_create_cloudflare_user(db, email=resolved_identity.email)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Legacy auth mode not supported in this plan.",
    )


def require_authenticated_user_id(
    user: AppUser = Depends(require_authenticated_user),
) -> str:
    return user.user_id

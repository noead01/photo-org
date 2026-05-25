from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.storage import user_role_assignments, users


CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"
AUTH_MODE_CLOUDFLARE_ACCESS = "cloudflare_access"


@dataclass(frozen=True)
class CloudflareAccessIdentity:
    email: str


@dataclass(frozen=True)
class AppUser:
    user_id: str
    email: str
    display_name: str | None
    roles: frozenset[str]


def normalize_email(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if candidate else None


def resolve_cloudflare_access_identity(email_header: str | None) -> CloudflareAccessIdentity:
    email = normalize_email(email_header)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )
    return CloudflareAccessIdentity(email=email)


def get_or_create_cloudflare_user(
    db: Session,
    *,
    email: str,
    subject: str | None = None,
) -> AppUser:
    normalized_email = normalize_email(email)
    if normalized_email is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )
    auth_subject = (subject or normalized_email).strip().lower()

    row = db.execute(
        select(users).where(users.c.auth_subject == auth_subject)
    ).mappings().one_or_none()
    if row is None:
        now = datetime.now(tz=UTC)
        user_id = str(uuid4())
        db.execute(
            insert(users).values(
                user_id=user_id,
                auth_provider=AUTH_MODE_CLOUDFLARE_ACCESS,
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
            select(user_role_assignments.c.role).where(
                user_role_assignments.c.user_id == row["user_id"]
            )
        ).scalars().all()
    )

    return AppUser(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        roles=assigned_roles,
    )

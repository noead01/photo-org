from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from app.auth import AppUser, derive_capabilities
from app.dependencies import get_db, require_authenticated_user, require_role
from app.storage import user_role_assignments, users


router = APIRouter(prefix="/admin", tags=["admin"])

RoleName = Literal["viewer", "contributor", "admin"]


class SessionCapabilitiesResponse(BaseModel):
    add_to_album: bool
    export: bool
    review_faces: bool
    manage_roles: bool
    manage_sources: bool


class SessionIdentityResponse(BaseModel):
    user_id: str
    email: str
    display_name: str | None
    roles: list[RoleName]
    capabilities: SessionCapabilitiesResponse


class AdminUserResponse(BaseModel):
    user_id: str
    auth_provider: str
    auth_subject: str
    email: str
    display_name: str | None
    roles: list[RoleName]
    created_ts: datetime
    updated_ts: datetime


class UpdateUserRolesRequest(BaseModel):
    roles: list[RoleName]


def _sorted_roles(values: set[str] | frozenset[str] | list[str]) -> list[RoleName]:
    ordered = sorted(set(values), key=lambda role: {"viewer": 1, "contributor": 2, "admin": 3}[role])
    return ordered  # type: ignore[return-value]


def _build_session_identity_response(user: AppUser) -> SessionIdentityResponse:
    capabilities = derive_capabilities(user)
    return SessionIdentityResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=_sorted_roles(user.roles),
        capabilities=SessionCapabilitiesResponse(
            add_to_album=capabilities.add_to_album,
            export=capabilities.export,
            review_faces=capabilities.review_faces,
            manage_roles=capabilities.manage_roles,
            manage_sources=capabilities.manage_sources,
        ),
    )


def _load_admin_user(db: Session, user_id: str) -> AdminUserResponse:
    row = db.execute(select(users).where(users.c.user_id == user_id)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    roles = db.execute(
        select(user_role_assignments.c.role).where(user_role_assignments.c.user_id == user_id)
    ).scalars().all()
    return AdminUserResponse(
        user_id=row["user_id"],
        auth_provider=row["auth_provider"],
        auth_subject=row["auth_subject"],
        email=row["email"],
        display_name=row["display_name"],
        roles=_sorted_roles(roles),
        created_ts=row["created_ts"],
        updated_ts=row["updated_ts"],
    )


@router.get(
    "/session",
    summary="Get current session",
    description="Return the authenticated application user, assigned roles, and derived UI capabilities.",
    response_model=SessionIdentityResponse,
)
def get_current_session_endpoint(
    user: AppUser = Depends(require_authenticated_user),
) -> SessionIdentityResponse:
    return _build_session_identity_response(user)


@router.get(
    "/users",
    summary="List users",
    description="Return provisioned application users and their assigned roles.",
    response_model=list[AdminUserResponse],
    responses={status.HTTP_403_FORBIDDEN: {"description": "Admin role required"}},
)
def list_users_endpoint(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_role("admin")),
) -> list[AdminUserResponse]:
    rows = db.execute(select(users).order_by(users.c.email.asc(), users.c.user_id.asc())).mappings().all()
    return [_load_admin_user(db, row["user_id"]) for row in rows]


@router.put(
    "/users/{user_id}/roles",
    summary="Replace user roles",
    description="Replace the assigned roles for one application user.",
    response_model=AdminUserResponse,
    responses={
        status.HTTP_403_FORBIDDEN: {"description": "Admin role required"},
        status.HTTP_404_NOT_FOUND: {"description": "User not found"},
    },
)
def replace_user_roles_endpoint(
    user_id: str,
    body: UpdateUserRolesRequest,
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_role("admin")),
) -> AdminUserResponse:
    existing = db.execute(select(users.c.user_id).where(users.c.user_id == user_id)).scalar_one_or_none()
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    now = datetime.now(tz=UTC)
    db.execute(delete(user_role_assignments).where(user_role_assignments.c.user_id == user_id))
    for role in _sorted_roles(body.roles):
        db.execute(
            insert(user_role_assignments).values(
                user_id=user_id,
                role=role,
                created_ts=now,
                updated_ts=now,
            )
        )
    db.execute(update(users).where(users.c.user_id == user_id).values(updated_ts=now))
    db.commit()
    return _load_admin_user(db, user_id)

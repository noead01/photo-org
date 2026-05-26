from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.request import urlopen
from uuid import uuid4

from fastapi import HTTPException, status
import jwt
from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.storage import user_role_assignments, users


CF_ACCESS_AUTHENTICATED_USER_EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"
CF_ACCESS_JWT_ASSERTION_HEADER = "Cf-Access-Jwt-Assertion"
AUTH_MODE_CLOUDFLARE_ACCESS = "cloudflare_access"
CLOUDFLARE_TEAM_DOMAIN_ENV = "PHOTO_ORG_CLOUDFLARE_TEAM_DOMAIN"
CLOUDFLARE_ACCESS_AUD_ENV = "PHOTO_ORG_CLOUDFLARE_ACCESS_AUD"
CLOUDFLARE_JWKS_CACHE_TTL_SECONDS_ENV = "PHOTO_ORG_CLOUDFLARE_JWKS_CACHE_TTL_SECONDS"
DEFAULT_CLOUDFLARE_JWKS_CACHE_TTL_SECONDS = 300
_CLOUDFLARE_JWKS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}


@dataclass(frozen=True)
class CloudflareAccessIdentity:
    email: str
    subject: str


@dataclass(frozen=True)
class CloudflareAccessConfig:
    team_domain: str
    audience: str
    issuer: str
    jwks_url: str
    cache_ttl_seconds: int


@dataclass(frozen=True)
class AppUser:
    user_id: str
    email: str
    display_name: str | None
    roles: frozenset[str]


@dataclass(frozen=True)
class AppCapabilities:
    add_to_album: bool
    export: bool
    review_faces: bool
    manage_roles: bool
    manage_sources: bool


def normalize_email(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if candidate else None


def get_cloudflare_access_config() -> CloudflareAccessConfig:
    team_domain = (os.getenv(CLOUDFLARE_TEAM_DOMAIN_ENV) or "").strip().lower()
    audience = (os.getenv(CLOUDFLARE_ACCESS_AUD_ENV) or "").strip()
    cache_ttl_raw = (os.getenv(CLOUDFLARE_JWKS_CACHE_TTL_SECONDS_ENV) or "").strip()

    if not team_domain or not audience:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloudflare Access auth misconfigured",
        )

    try:
        cache_ttl_seconds = (
            int(cache_ttl_raw) if cache_ttl_raw else DEFAULT_CLOUDFLARE_JWKS_CACHE_TTL_SECONDS
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cloudflare Access auth misconfigured",
        ) from exc

    return CloudflareAccessConfig(
        team_domain=team_domain,
        audience=audience,
        issuer=f"https://{team_domain}",
        jwks_url=f"https://{team_domain}/cdn-cgi/access/certs",
        cache_ttl_seconds=max(cache_ttl_seconds, 0),
    )


def fetch_cloudflare_access_jwks(team_domain: str) -> dict[str, object]:
    url = f"https://{team_domain}/cdn-cgi/access/certs"
    with urlopen(url, timeout=5) as response:
        return json.load(response)


def _get_cached_cloudflare_access_jwks(
    config: CloudflareAccessConfig,
    *,
    force_refresh: bool = False,
) -> dict[str, object]:
    cache_key = config.team_domain
    cached = _CLOUDFLARE_JWKS_CACHE.get(cache_key)
    now = time.monotonic()
    if (
        not force_refresh
        and cached is not None
        and now - cached[0] < config.cache_ttl_seconds
    ):
        return cached[1]

    jwks = fetch_cloudflare_access_jwks(config.team_domain)
    _CLOUDFLARE_JWKS_CACHE[cache_key] = (now, jwks)
    return jwks


def _lookup_cloudflare_access_signing_key(
    config: CloudflareAccessConfig,
    kid: str | None,
) -> object:
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )

    for force_refresh in (False, True):
        jwks = _get_cached_cloudflare_access_jwks(config, force_refresh=force_refresh)
        for jwk in jwks.get("keys", []):
            if isinstance(jwk, dict) and jwk.get("kid") == kid:
                return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Authenticated user required",
    )


def validate_cloudflare_access_jwt(jwt_assertion: str) -> dict[str, object]:
    config = get_cloudflare_access_config()
    try:
        header = jwt.get_unverified_header(jwt_assertion)
        signing_key = _lookup_cloudflare_access_signing_key(config, header.get("kid"))
        return jwt.decode(
            jwt_assertion,
            key=signing_key,
            algorithms=["RS256"],
            audience=config.audience,
            issuer=config.issuer,
        )
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        ) from None


def resolve_cloudflare_access_identity(
    jwt_assertion: str | None,
    email_header: str | None,
) -> CloudflareAccessIdentity:
    if not jwt_assertion:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )

    claims = validate_cloudflare_access_jwt(jwt_assertion)
    subject = str(claims.get("sub") or "").strip()
    email = normalize_email(claims.get("email"))
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )

    normalized_header_email = normalize_email(email_header)
    if normalized_header_email is not None and normalized_header_email != email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user required",
        )

    return CloudflareAccessIdentity(email=email, subject=subject)


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


def derive_capabilities(user: AppUser) -> AppCapabilities:
    user_rank = max(
        ({"viewer": 1, "contributor": 2, "admin": 3}.get(role, 0) for role in user.roles),
        default=0,
    )
    return AppCapabilities(
        add_to_album=True,
        export=True,
        review_faces=user_rank >= 2,
        manage_roles=user_rank >= 3,
        manage_sources=user_rank >= 3,
    )

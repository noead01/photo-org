from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


TEAM_DOMAIN = "example.cloudflareaccess.com"
ACCESS_AUDIENCE = "photo-org-access-aud"
ISSUER = f"https://{TEAM_DOMAIN}"
KEY_ID = "test-key-1"


@lru_cache(maxsize=1)
def _private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@lru_cache(maxsize=1)
def _private_key_pem() -> str:
    pem = _private_key().private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem.decode("utf-8")


@lru_cache(maxsize=1)
def _public_jwk() -> dict[str, object]:
    algorithm = jwt.algorithms.RSAAlgorithm(jwt.algorithms.RSAAlgorithm.SHA256)
    jwk_json = algorithm.to_jwk(_private_key().public_key(), as_dict=False)
    jwk = json.loads(jwk_json)
    jwk.update({"use": "sig", "kid": KEY_ID, "alg": "RS256"})
    return jwk


def configure_cloudflare_access_env(monkeypatch) -> None:
    monkeypatch.setenv("PHOTO_ORG_AUTH_MODE", "cloudflare_access")
    monkeypatch.setenv("PHOTO_ORG_CLOUDFLARE_TEAM_DOMAIN", TEAM_DOMAIN)
    monkeypatch.setenv("PHOTO_ORG_CLOUDFLARE_ACCESS_AUD", ACCESS_AUDIENCE)
    monkeypatch.setenv("PHOTO_ORG_CLOUDFLARE_JWKS_CACHE_TTL_SECONDS", "300")


def build_access_jwt(
    *,
    subject: str,
    email: str,
    audience: str = ACCESS_AUDIENCE,
    expires_in_seconds: int = 300,
) -> str:
    now = datetime.now(tz=UTC)
    claims = {
        "iss": ISSUER,
        "sub": subject,
        "aud": [audience],
        "email": email,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(claims, _private_key_pem(), algorithm="RS256", headers={"kid": KEY_ID})


def stub_cloudflare_access_certs(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.auth.fetch_cloudflare_access_jwks",
        lambda *_args, **_kwargs: {"keys": [_public_jwk()]},
    )

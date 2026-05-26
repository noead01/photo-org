# Cloudflare Access JWT Validation Design

## Goal

Harden `PHOTO_ORG_AUTH_MODE=cloudflare_access` so the backend trusts only a validated `Cf-Access-Jwt-Assertion`, not a caller-supplied email header.

## Scope

- Require JWT validation in `cloudflare_access` mode.
- Keep `legacy_headers` as the only local/dev fallback mode.
- Validate Access JWTs against Cloudflare's published certs for the configured team domain.
- Verify `iss`, `aud`, `exp`, and signature before resolving an app user.
- Use JWT `sub` as `users.auth_subject`.
- Require an `email` claim for the current app user model and admin UI.

## Non-Goals

- No Cloudflare group sync.
- No offline static-key mode in this slice.
- No UI changes.

## Configuration

- `PHOTO_ORG_CLOUDFLARE_TEAM_DOMAIN`
  Example: `example.cloudflareaccess.com`
- `PHOTO_ORG_CLOUDFLARE_ACCESS_AUD`
  The Access application audience tag.
- `PHOTO_ORG_CLOUDFLARE_JWKS_CACHE_TTL_SECONDS`
  Optional in-memory cert cache TTL, default `300`.

## Request Flow

In `cloudflare_access` mode:

1. Read `Cf-Access-Jwt-Assertion`.
2. Load Cloudflare certs from `https://<team-domain>/cdn-cgi/access/certs`, with a short in-memory cache.
3. Verify JWT signature and claims.
4. Extract `sub` and `email` from verified claims.
5. Optionally compare `Cf-Access-Authenticated-User-Email` to the validated `email` claim and reject on mismatch.
6. Resolve or auto-provision the app user using:
   - `auth_provider = cloudflare_access`
   - `auth_subject = sub`
   - `email = normalized email claim`

In `legacy_headers` mode, keep the existing local header-driven behavior unchanged.

## Failure Behavior

- Missing JWT in `cloudflare_access`: `403 Authenticated user required`
- Invalid signature / issuer / audience / expiry: `403 Authenticated user required`
- Missing required Cloudflare config in `cloudflare_access`: `500 Cloudflare Access auth misconfigured`
- Missing `email` or `sub` claim after validation: `403 Authenticated user required`
- Header/email mismatch after validation: `403 Authenticated user required`

## Testing

- Valid JWT provisions a user keyed by `sub`.
- Missing JWT is rejected in `cloudflare_access`.
- Invalid `aud` is rejected.
- Valid JWT plus role assignment still authorizes protected/admin endpoints.
- `legacy_headers` mode continues to work for local tests.

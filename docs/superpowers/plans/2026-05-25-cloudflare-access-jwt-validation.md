# Cloudflare Access JWT Validation Plan

## Goal

Require verified Cloudflare Access JWTs in `cloudflare_access` mode while preserving `legacy_headers` as the separate local/dev fallback mode.

## Tasks

### 1. Add failing auth tests

- Extend `apps/api/tests/test_auth_rbac.py` with:
  - missing JWT rejected in `cloudflare_access`
  - valid JWT provisions user by `sub`
  - invalid audience rejected
  - valid JWT authorizes session/admin endpoint with DB roles

### 2. Implement JWT validation helpers

- Update `apps/api/app/auth.py` with:
  - `CF_ACCESS_JWT_ASSERTION_HEADER`
  - Cloudflare config loader
  - cert fetch and cache helper
  - JWT verification and claim extraction
  - identity resolver returning validated `sub` and `email`

### 3. Wire dependencies to validated identity

- Update `apps/api/app/dependencies.py` so `cloudflare_access` reads `Cf-Access-Jwt-Assertion`, validates it, and resolves the app user from verified claims.
- Remove plain email-header trust from authorization decisions in this mode.

### 4. Wire runtime config

- Update `apps/api/pyproject.toml` with the JWT dependency.
- Update `compose.yaml` and `.env.compose.example` to document/pass Cloudflare JWT validation env vars.

### 5. Verify

- Run:
  - `uv run python -m pytest apps/api/tests/test_auth_rbac.py apps/api/tests/test_face_assignment_api.py apps/api/tests/test_albums_and_exports_api.py apps/api/tests/test_main.py -q`

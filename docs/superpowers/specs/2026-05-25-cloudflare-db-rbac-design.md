# Cloudflare DB RBAC Design

## Goal

Replace header-based application authorization with database-backed global user roles for Cloudflare-authenticated users, while auto-provisioning user records on first access and preserving a narrow first implementation scope.

## Scope

This design covers:

- database-backed user identity records
- global role assignments stored in the database
- Cloudflare-authenticated request resolution to an app user
- route-level authorization for existing protected API surfaces
- album ownership based on app user records

This design does not cover:

- team or group membership modeling
- JWT validation of `Cf-Access-Jwt-Assertion`
- an admin UI for managing users or roles
- synchronization from Cloudflare or IdP groups into app roles

## Current State

The current app has no durable user or role model.

- face-labeling permissions are enforced from `X-Face-Validation-Role`
- album ownership and membership attribution use raw string fields such as `owner_user_id` and `added_by_user_id`
- Cloudflare Access identity is not yet mapped to a database principal

This means authenticated users can enter through Cloudflare, but the app still lacks an internal trust boundary for authorization and ownership.

## Requirements

The first implementation must satisfy these requirements:

1. Cloudflare-authenticated users resolve to a durable app user record.
2. First-time users are auto-created in the database with no implicit elevated privileges.
3. Authorization decisions use database role assignments, not client-supplied headers.
4. Roles are global per user, not scoped by team, album, or resource.
5. Existing protected API surfaces must use the resolved app user and role set.
6. Album ownership and attribution for new writes must use the app `user_id`.

## Chosen Approach

Use a `users` table plus a `user_role_assignments` table.

This approach keeps identity and authorization separate:

- the `users` table stores the durable principal
- the `user_role_assignments` table stores zero or more global roles

This is preferred over a single `users.role` column because the app already has more than one privilege tier and will likely accumulate more authorization checks over time. It is also preferred over a fully normalized `roles` catalog because the role set is currently small and stable.

## Data Model

### Users

Add a `users` table with:

- `user_id`: primary key
- `auth_provider`: string, initially `cloudflare_access`
- `auth_subject`: unique external identity key
- `email`: unique normalized email
- `display_name`: nullable display string
- `created_ts`
- `updated_ts`

Identity resolution should prefer a stable external subject when one is available from the trusted Cloudflare identity boundary. If the first cut only has a trusted email available, email may temporarily serve as the unique identity key. The design should keep `auth_subject` distinct so the implementation can move away from email-as-identity without redesigning the table.

### User Role Assignments

Add a `user_role_assignments` table with:

- `user_id`: foreign key to `users.user_id`
- `role`: constrained string
- `created_ts`
- `updated_ts`

The table should enforce uniqueness on `(user_id, role)`.

The allowed role set for the first cut is fixed in code and constrained in the schema:

- `viewer`
- `contributor`
- `admin`

## Authorization Semantics

Roles are global and cumulative:

- `viewer`: read-only app usage such as browsing, searching, and reading owned albums
- `contributor`: viewer capabilities plus face-labeling actions
- `admin`: contributor capabilities plus admin/configuration actions

The API authorization layer should expose dependencies along these lines:

- `require_authenticated_user()`
- `require_role("contributor")`
- `require_role("admin")`

These dependencies must resolve a database user first, then derive effective permissions from `user_role_assignments`.

## Request Flow

In `cloudflare_access` mode:

1. Read trusted Cloudflare-authenticated identity metadata at the API boundary.
2. Normalize the external identity.
3. Look up an existing `users` row.
4. If no row exists, create one automatically with no role assignments.
5. Load that user’s roles from `user_role_assignments`.
6. Attach the resolved app user to request processing.
7. Route dependencies enforce required roles from the resolved app user.

In this model, authentication and authorization are separate:

- authentication determines who the user is
- authorization determines what the user may do

## Protected Surfaces

### Albums

Album APIs must stop trusting `X-Photo-Org-User-Id`.

In `cloudflare_access` mode:

- new albums store `owner_user_id` as the resolved app `user_id`
- new album item rows store `added_by_user_id` as the resolved app `user_id`
- album reads and mutations are scoped by the resolved app `user_id`

For the first cut, `owner_user_id` and `added_by_user_id` remain string columns. Their meaning changes to “app user id” for new writes instead of “raw caller-provided string”.

### Face Labeling

Face-labeling APIs must stop trusting `X-Face-Validation-Role`.

In `cloudflare_access` mode:

- privileged write actions require `contributor` or `admin`
- a user with no role assignments receives `403`

### Admin Surfaces

Any existing or future admin/configuration routes should require `admin`. This includes storage-source management and similar operational mutation surfaces once they are wired into the same dependency model.

## Migration Strategy

The first cut should not attempt a broad ownership backfill or a destructive schema rewrite.

Instead:

1. Add `users`
2. Add `user_role_assignments`
3. Keep `owner_user_id` and `added_by_user_id` as-is structurally
4. Change runtime write semantics so new values store app `user_id`

This keeps the migration low-risk and avoids coupling RBAC delivery to historical data cleanup.

## Error Handling

In `cloudflare_access` mode:

- missing trusted identity: `403`
- authenticated user with insufficient role: `403`
- ownership-protected resource belonging to another user: `404`

Invalid DB role values should be prevented by schema constraints and migration checks rather than handled permissively at runtime.

## Compatibility

The app may temporarily retain a `legacy_headers` mode for local development or transitional use, but the long-term target is to remove client-controlled authorization headers from application trust decisions.

The first implementation should keep the auth mode boundary explicit so tests can cover both legacy and Cloudflare-backed behavior during the transition.

## Testing

The implementation must add or update tests for:

- schema and migration coverage for `users` and `user_role_assignments`
- first-request auto-provisioning of users
- contributor/admin enforcement on protected write routes
- no-role denial for privileged actions
- album ownership and scoping via DB user ids
- legacy-mode compatibility during the transition

## Future Work

This design intentionally leaves these items for later:

- signed JWT validation for Cloudflare Access identity
- group-based RBAC synchronization
- role management APIs or UI
- historical backfill of old ownership string values
- richer capability modeling beyond the three initial global roles

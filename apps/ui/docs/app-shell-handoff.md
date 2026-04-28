# App Shell Handoff Expectations

Story: #164 (`Implement app shell frame with global header/nav/content regions`)

The shell contract for all primary routes is:

- Header and primary navigation remain mounted across route transitions.
- Route-level loading states render inside content only.
- Route-level errors render inside content only.
- Route transitions swap only content-region children while preserving shell frame continuity.

The implementation source of truth is `src/routes/routeDefinitions.ts` under each route `handoff` field.

# Account Menu Handoff Expectations

Story: #165 (`Implement logged-in user menu and account action entry points`)

The shell account surface behavior is:

- When session identity context exists, header shows signed-in identity name and email.
- Account actions are exposed through a keyboard-focusable `Account` button with:
  - `Account settings (coming soon)` placeholder entry point
  - `Sign out` entry point
- Selecting `Sign out` transitions shell identity into the deterministic fallback state.

Fallback behavior for missing identity context:

- Header shows `Session unavailable`.
- Account action button is disabled with accessible label `Account actions unavailable`.

Bootstrap notes:

- `window.__PHOTO_ORG_SESSION__` may provide initial identity payload.
- When no bootstrap value is set, UI uses deterministic local demo identity.
- Invalid bootstrap payload or explicit `null` uses fallback state.

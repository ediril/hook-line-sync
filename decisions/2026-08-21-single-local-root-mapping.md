# One local root per profile

Date: 2026-08-21

## Decision

Each profile has at most one canonical absolute local root. A descendant maps
to the identical profile-relative path beneath the profile's remote root.
Local roots belonging to different profiles may not equal, contain, or be
contained by one another.

`hlsync create` always records a local root. `--local-root PATH` supplies it
directly. Otherwise, `create` proposes the current directory and defaults its
confirmation to yes; declining prompts for another local folder.

`hlsync map <profile>` is the single editor for the local-to-remote mapping.
With no root options it proposes the current directory as the local root.
`--local-root` and `--remote-root` may change either or both sides. Proposed
changes are validated together, displayed as old → new, and require
confirmation that defaults to no. Rules, credentials, and endpoint settings
are preserved.

## Rationale

One root correspondence makes path translation mechanical and lets the current
directory identify exactly one profile. Rejecting overlap preserves that
invariant across every command.

## Intentionally excluded

- Multiple local mappings within one profile.
- Creating an unmapped profile through `hlsync create`.
- Persisted current-profile or directory-context state.
- Silently replacing a mapping or accepting overlapping roots.
- Updating the host, protocol, port, or credential variables through `map`.

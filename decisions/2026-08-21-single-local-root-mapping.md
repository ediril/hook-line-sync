# One local root per profile

Date: 2026-08-21

## Decision

Each profile has at most one canonical absolute local root. A descendant maps
to the identical project-relative path beneath the profile's remote root.
Local roots belonging to different profiles may not equal, contain, or be
contained by one another.

`hlsync add` proposes the current directory as the local root and defaults its
confirmation to yes. `hlsync map <profile>` maps the current directory later;
replacing an existing root requires confirmation and defaults to no.

## Rationale

One root correspondence makes path translation mechanical and lets the current
directory identify exactly one profile. Rejecting overlap preserves that
invariant across every command.

## Intentionally excluded

- Multiple local mappings within one profile.
- Persisted current-profile or directory-context state.
- Silently replacing a mapping or accepting overlapping roots.

# One local root per profile

Date: 2026-08-21

## Decision

Each profile has at most one canonical absolute local root. A descendant maps
to the identical project-relative path beneath the profile's remote root.
Local roots belonging to different profiles may not equal, contain, or be
contained by one another.

`hlsync add` always records a local root. `--local-root PATH` supplies it
directly. Otherwise, `add` proposes the current directory and defaults its
confirmation to yes; declining prompts for another local folder. `hlsync map
<profile>` maps older unmapped configurations or replaces an existing root;
replacement requires confirmation and defaults to no.

## Rationale

One root correspondence makes path translation mechanical and lets the current
directory identify exactly one profile. Rejecting overlap preserves that
invariant across every command.

## Intentionally excluded

- Multiple local mappings within one profile.
- Creating an unmapped profile through `hlsync add`.
- Persisted current-profile or directory-context state.
- Silently replacing a mapping or accepting overlapping roots.

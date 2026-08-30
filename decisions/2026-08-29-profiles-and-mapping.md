# Profiles and mapping

Date: 2026-08-29

## Decision

Each configured entry is a deployment profile, not a server. A profile owns
its protocol and endpoint, credential environment-variable names, absolute
remote root, and at most one canonical absolute local root. Profiles may share
a host, but their local roots may not equal, contain, or be contained by one
another. Every descendant keeps the same profile-relative path beneath the
remote root.

`hlsync create` always records a local root. It accepts `--local-root` directly
or proposes the current directory with yes as the default; declining prompts
for another directory. A profile without a local root cannot synchronize or
own rules and must be completed through `map`.

`hlsync map` is the single editor for the local-to-remote mapping. With no root
options it proposes the real current directory as the local root. Explicit
`--local-root` and `--remote-root` options may change either or both sides.
HLSync validates the complete proposed mapping, displays each old → new value,
and requires confirmation that defaults to no. Mapping changes preserve the
profile's rules, endpoint, and credential settings.

A profile-aware command either names a profile explicitly or resolves the one
mapped root containing the current directory. No profile selection persists
between commands. Commands requiring a profile fail outside mapped roots;
`hlsync profile` instead reports that no profile is active. Removing a profile
deletes only its local configuration and never connects to its endpoint.

## Rationale

The complete local-to-remote target is the meaningful safety boundary; a host
alone cannot distinguish deployments. One non-overlapping local root makes
path translation and current-directory inference deterministic. Requiring the
command or filesystem context to identify the profile prevents hidden state
from redirecting a transfer.

## Intentionally excluded

- Treating a configured entry as a deduplicated server record.
- Multiple or overlapping local roots.
- Creating a new unmapped profile.
- A global or directory-scoped `use` setting.
- Guessing a profile or falling back to the first configured profile.
- Silently changing a mapping or editing endpoint settings through `map`.
- Storing credential values in profile configuration.
- Connecting to or deleting remote content when a profile is removed.

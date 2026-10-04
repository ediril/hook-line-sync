# Profiles and mapping

Date: 2026-08-29

## Decision

Each configured entry is a deployment profile, not a server. A profile owns
its protocol and endpoint, credential environment-variable names, absolute
remote root, and at most one canonical absolute local root. Profiles may share
a host, but their local roots may not equal, contain, or be contained by one
another. Every descendant keeps the same profile-relative path beneath the
remote root.

Configuration stores these entries under the `profiles` key in
`~/.hlsync/configs.json`, using schema version 9. The model and public APIs use
profile terminology consistently; there is no parallel project representation.
Earlier runtime names and configuration schemas are not recognized or migrated.

New profiles always record a local root. A profile without a local root cannot
synchronize or own rules and must be completed through mapping.

Mapping changes validate the complete proposed local-to-remote target and
require explicit confirmation. They preserve the profile's rules, endpoint,
and credential settings.

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

A clean schema break is preferable while the tool is pre-alpha because it
avoids aliases and migration paths for representations that no longer match
the model. Current runtime names and CLI usage are documented in README.

## Intentionally excluded

- Treating a configured entry as a deduplicated server record.
- Multiple or overlapping local roots.
- Creating a new unmapped profile.
- A global or directory-scoped `use` setting.
- Guessing a profile or falling back to the first configured profile.
- Silently changing a mapping or editing endpoint settings through `map`.
- Storing credential values in profile configuration.
- Reading or migrating legacy runtime configuration and project schemas.
- Connecting to or deleting remote content when a profile is removed.

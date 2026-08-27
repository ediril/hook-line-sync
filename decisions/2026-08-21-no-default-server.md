# No default profile

Date: 2026-08-21

## Decision

Hook Line Sync does not persist a default profile. A command either names a
profile explicitly where that command permits it, or resolves the one unique
mapped local root containing the current directory. An unmapped or ambiguous
location is an error.

## Rationale

An ambient default can redirect a transfer without the command or working
directory revealing its destination. Filesystem context keeps destination
selection visible and deterministic.

## Intentionally excluded

- A global or directory-scoped `use` setting.
- Guessing a profile when resolution has no unique answer.
- Falling back to the first configured profile.

# Push and pull execution

Date: 2026-08-21

## Decision

Push creates required remote parents and uploads local-only or changed files.
Each upload uses a unique temporary name, verifies size, applies the local
whole-second UTC timestamp with MFMT, and renames into place. Replacement keeps
a temporary backup until installation succeeds.

Pull replaces changed local files but never downloads remote-only paths. Each
download is written and synced beside its destination, verifies size, preserves
existing local permissions, applies the remote timestamp, and atomically
renames into place.

Explicit push pruning deletes remote-only files and then directories deepest
first, only after every planned upload succeeds. Type and symlink conflicts
reject the plan before mutation. A path-scoped permission failure skips that
path or unwritable subtree, continues independent work, suppresses all pruning,
and produces a nonzero exit. A session failure or failed replacement recovery
aborts because subsequent remote state cannot be trusted.

## Rationale

Per-file staging makes replacement recoverable within FTP's capabilities.
Timestamp preservation prevents a successful transfer from immediately
comparing as changed, and delete-last ordering keeps old remote content until
new content is safely present.

## Intentionally excluded

- Project-wide transaction guarantees, which FTP cannot provide.
- Continuing after the session or replacement state becomes untrustworthy.
- Persistently excluding a path merely because one transfer lacked permission.
- Pruning after any upload failure.

# Push and pull execution

Date: 2026-08-21

## Decision

Push creates required remote parents and uploads local-only or changed files.
Each upload uses a unique temporary name, verifies size, applies the local
whole-second UTC timestamp with MFMT, reads it back independently with MDTM at
the server's reported precision, and only then renames into place. A successful
MFMT reply acknowledges the command but is not itself timestamp verification.
Replacement keeps a temporary backup until installation succeeds.

Before a push comparison, HLSync recovers exact reserved artifacts within the
selected scope. An abandoned upload is deleted. A backup is deleted when its
destination exists and restored when the destination is absent. This recovery
is lifecycle management of HLSync-owned files and never requires remote-prune
authorization.

Pull replaces changed local files but never downloads remote-only paths. Each
download is written and synced beside its destination, verifies size, preserves
existing local permissions, applies the remote timestamp, and atomically
renames into place.

Immediately before each remote mutation or local replacement, execution emits
a semantic operation event. The CLI renders these as plain-language `Adding`,
`Updating`, `Creating`, or `Deleting` lines and flushes them immediately. A
successful command ends with a compact count and reports retained remote-only
paths, but does not repeat the complete comparison model. A command with no
executable actions reports that there is nothing to push or pull and omits the
empty transfer-phase heading. The zero-action result is indented like streamed
operations; push also reports the number of unchanged included files in the
selected scope, without implying that an uninspected project is synchronized.
Push-only retained paths include an explicit `-p` pruning hint without
enumerating the paths again; pull never suggests remote deletion.

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
new content is safely present. Streaming the attempted operation identifies a
slow or failed path without presenting an operation as already successful.

## Intentionally excluded

- Project-wide transaction guarantees, which FTP cannot provide.
- Continuing after the session or replacement state becomes untrustworthy.
- Persistently excluding a path merely because one transfer lacked permission.
- Pruning after any upload failure.
- Trusting server-specific MFMT response text as evidence of the applied time.
- Concurrent pushes to the same profile; artifact recovery assumes one active
  push per profile.
- Reprinting internal comparison actions after a successful transfer.

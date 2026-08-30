# Push and pull execution

Date: 2026-08-30

## Decision

Push creates required remote parents and uploads local-only or changed files.
Each upload uses a unique temporary name beside its destination, verifies size,
applies the local whole-second UTC timestamp with MFMT, reads it back through
MDTM at the server's reported precision, and only then renames it into place.
Replacement keeps a temporary backup until installation succeeds.

Artifact recovery is part of the selected push snapshot. When the ordinary
comparison traversal reads a remote directory, it resolves exact HLSync-owned
artifacts in that directory before comparing its contents, then re-reads only
that directory if recovery changed it. Recovery does not run as a separate
recursive scan and does not descend into a directory merely to seek artifacts.
An abandoned upload is deleted. A backup is deleted when its destination exists
and restored when the destination is absent. This lifecycle management never
depends on the remote-only retention option.
Remote-excluded directories are never entered, including for artifact
recovery.

Pull replaces changed local files but never downloads remote-only paths. Each
download is written and synced beside its destination, verifies size, preserves
existing local permissions, applies the remote timestamp, and atomically
renames into place.

Immediately before each remote mutation or local replacement, execution emits
a semantic operation event. The CLI renders these as plain-language `Adding`,
`Updating`, `Creating`, or `Deleting` lines and flushes them immediately. A
successful command ends with a compact count. A zero-action result is
indented like streamed operations and reports the number of unchanged included
files actually inspected. A push using `--keep-remote` confirms retention
without repeating paths already available through diff.

Push deletes selected remote-only files and then directories deepest first,
only after every planned upload succeeds. `--keep-remote` suppresses those
deletions. Type and symlink conflicts reject the plan before mutation. A
path-scoped permission failure skips that path or unwritable subtree, continues
independent work, suppresses all deletion, and produces a nonzero exit. A
session failure or failed replacement recovery aborts because subsequent remote
state cannot be trusted.

## Rationale

Per-file staging makes replacement recoverable within FTP's capabilities.
Timestamp preservation prevents a successful transfer from immediately
comparing as changed, and delete-last ordering keeps old remote content until
new content is safely present. Integrating recovery into comparison traversal
preserves those guarantees without paying for a second remote-tree walk before
the user sees useful progress.

## Intentionally excluded

- A profile-wide artifact sweep unrelated to the paths traversed by the push.
- Project-wide transaction guarantees, which FTP cannot provide.
- Continuing after the session or replacement state becomes untrustworthy.
- Persistently excluding a path merely because one transfer lacked permission.
- Pruning after any upload failure.
- Trusting server-specific MFMT response text as evidence of the applied time.
- Concurrent pushes to the same profile.
- Reprinting internal comparison actions after a successful transfer.

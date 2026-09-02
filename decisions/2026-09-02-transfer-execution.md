# Transfer execution

Date: 2026-09-02

## Decision

Push, pull, and dry push consume one deterministic ordered operation stream.
The transfer executor performs preflight, emits each operation immediately
before its mutation boundary, and preserves create-before-upload and
delete-files-before-delete-directories ordering. Dry push runs that same push
executor with mutations disabled; it reports and counts the same operations but
does not create, upload, replace, change timestamps, or delete.

Push uploads through a unique staging file beside the destination, verifies its
size and server-observed timestamp, and then installs it by rename. Replacement
keeps a temporary backup until installation succeeds. Artifact recovery occurs
while selected remote directories are read. Live push repairs exact
HLSync-owned artifacts; dry push projects those repairs into its snapshot
without mutating them. Remote-excluded directories are never entered for
recovery or transfer.

Pull replaces only changed existing local files. It downloads and syncs a
temporary file beside the destination, verifies size, preserves local
permissions, applies the remote timestamp, and atomically renames it into
place.

Push deletes selected remote-only files and then directories deepest first,
only after all uploads succeed. `--keep-remote` suppresses those deletions. A
path-scoped permission failure skips that path or unwritable subtree, continues
independent work, suppresses deletion, and produces a nonzero exit. A session
failure or failed replacement recovery stops execution because subsequent
remote state cannot be trusted.

## Rationale

Running dry push through the live executor prevents preview and feedback from
drifting away from actual execution. Per-file staging makes replacement
recoverable within FTP's capabilities. Delete-last ordering keeps existing
remote content until new content is safely installed, while traversal-scoped
artifact recovery avoids a separate remote-tree sweep.

## Intentionally excluded

- Invoking any transfer mutation from dry-run mode.
- A profile-wide artifact sweep unrelated to selected traversal.
- Project-wide transaction guarantees, which FTP cannot provide.
- Continuing after session or replacement state becomes untrustworthy.
- Persistently excluding a path because one transfer lacked permission.
- Pruning after any upload failure.
- Concurrent pushes to the same profile.

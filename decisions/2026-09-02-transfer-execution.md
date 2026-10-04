# Transfer execution

Date: 2026-09-02

## Decision

Push, pull, and dry push consume one deterministic ordered operation stream.
The executor performs preflight and preserves create-before-upload and
file-before-directory deletion ordering. Dry push uses that same executor with
mutations disabled, including timestamp changes and artifact recovery.

Push uploads through a unique staging file beside the destination, verifies
size and server-observed timestamp, and installs it by rename. Replacement
keeps a temporary backup until installation succeeds. Timestamp capabilities
and read-back guarantees are defined in the
[remote metadata decision](2026-09-13-remote-listings.md); remote permissions
remain governed by [server policy](2026-09-13-server-permissions.md).

Artifact recovery occurs while selected remote directories are read. Live push
repairs exact HLSync-owned artifacts; dry push projects those repairs into its
snapshot without mutation. Remote-excluded directories are never entered for
recovery or transfer. Reserved artifacts use the `.hlsync-` namespace; artifacts
from obsolete runtime names are not recovered.

Pull replaces only changed existing local files. It downloads and syncs a
temporary file beside the destination, verifies size, preserves local
permissions, applies the remote timestamp, and atomically renames it into place.

Push deletes selected remote-only files and then directories deepest first,
only after all uploads succeed. Retention policy suppresses those deletions.
A path-scoped permission failure skips that path or unwritable subtree,
continues independent work, suppresses deletion, and produces a nonzero exit.
A session failure or failed replacement recovery stops execution because
subsequent remote state cannot be trusted. A file failure alone does not prove
that its containing directory is unwritable.

The executor emits successful-operation events after completion and failure or
skip events when their outcomes are known. Dry push uses the same callback for
planned operations. Byte-send events belong to the transport; bytes sent are
not installed files until verification and rename finish. Display observes these
events and never decides transfer completion or pruning eligibility.

Traversal reports discovered and completed directories from the same selected
walk, after exclusion filtering and artifact handling. Progress must not trigger
a second traversal, enter protected trees, or modify the plan. Marker spelling,
refresh rates, summaries, and optional tips belong in README and commit history.

## Rationale

A shared executor prevents dry-run plans from drifting away from execution.
Per-file staging makes replacement recoverable within FTP's capabilities.
Delete-last ordering preserves remote content until uploads are safely
installed, while traversal-scoped recovery avoids an unrelated tree sweep.

Outcome events keep completion authority in the executor and make failures
observable while independent work continues. Separate byte and installation
events prevent presentation from claiming success before verification.

## Intentionally excluded

- Mutations in dry-run mode or treating a dry run as a write-permission check.
- A profile-wide artifact sweep or preliminary traversal to count work.
- Project-wide transactions, concurrent pushes, or resumable partial uploads.
- Continuing after session or replacement state becomes untrustworthy.
- Persistently excluding a path because a transfer lacked permission.
- Pruning after an upload failure or counting failed files as installed.

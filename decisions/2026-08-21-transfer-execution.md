# Push and pull execution

Date: 2026-08-21

## Decision

Push and pull take fresh selected snapshots, build the same comparison plan
shown by `hlsync diff`, reject the entire plan if it contains a type or symlink
conflict, and then execute its selected actions. Bare push includes the complete
current subtree and is equivalent to `hlsync push -r`; preview it with
`hlsync diff -r`. Pull requires an explicit file, directory, or pattern operand;
`hlsync pull .` explicitly selects the current directory. A directory operand
remains shallow unless `-r` is supplied. A literal or wildcard selector limits
both transfer and prune actions to matching paths.

Push creates required remote parent directories, uploads local-only files, and
replaces changed remote files. Each upload is staged under a unique temporary
name, checked for size, assigned the local whole-second UTC timestamp with
MFMT, and renamed into place. Replacement first renames the prior file to a
unique backup so it can be restored if installation fails.

Pull replaces changed local files but does not download remote-only paths. Each
download is written and synced to a temporary file beside its destination,
checked for size, assigned the remote timestamp and existing local permissions,
and atomically renamed over the destination.

`--prune-remote` / `-p` deletes remote-only files and then directories deepest
first. Deletes run only after every planned upload succeeds.

A path-scoped FTPS permission failure is recorded without ending a push.
Failure to create a directory skips its descendants, while independent paths
continue. The command returns a nonzero status with completed, failed, and
skipped counts. Any upload failure suppresses the complete pruning phase, and
no failure becomes a persistent exclusion. Session failures and replacement
failures whose backup cannot be restored remain fatal because the connection or
remote state is no longer trustworthy.

## Rationale

Staging makes each file replacement recoverable without requiring unsupported
cross-system transactions. Timestamp verification keeps a completed push from
immediately comparing as changed. Preflight conflict and local-source checks
avoid starting a known-invalid plan, while delete-last ordering preserves old
remote content until replacements are present.

## Consequences

- The FTPS server must support MFMT as well as MLSD for push.
- Changed files are overwritten in the command's explicit direction; diff
  is the preview mechanism.
- Transfers are atomic per file, not across the whole project. FTPS has no
  project-wide transaction, so path-scoped permission failures leave earlier
  successful files in place and allow independent later files to continue.
- Local files selected for upload or replacement are revalidated before any
  mutation. A concurrent local change aborts the plan.
- Symlinks and file/directory type changes are conflicts and cause no mutation.
- Remote-only paths are always reported and require `-p` for deletion.
- Excluded paths never enter snapshots or plans. An excluded descendant may
  keep an otherwise remote-only directory non-empty, causing safe prune failure
  rather than deletion of excluded content.

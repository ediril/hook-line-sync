# Comparison and transfer planning

Date: 2026-08-30

## Decision

`hlsync diff` is a read-only projection of the actions a transfer would take
over the selected scope. Its default push perspective treats local existence as
authoritative: local-only paths are created remotely, changed files are
replaced, and remote-only paths are deleted. `-k` / `--keep-remote` changes
remote-only actions to retention. `--pull` reverses replacement direction but
never restores missing local paths or deletes remote paths.

Diff and transfer commands share selection and planning semantics. A transfer
always takes fresh snapshots and builds a new plan immediately before mutation;
displayed output is never an executable cached plan. Excluded local paths are
treated as absent from the authoritative set, so a selected remote counterpart
is deleted by default and retained under `--keep-remote`.
Remote exclusions are synchronization boundaries instead: the planner emits a
non-executable excluded entry for the boundary and suppresses every operation
beneath an excluded remote directory.

## Rationale

A deployment push that leaves renamed or deliberately removed files behind does
not synchronize the destination. Making exact synchronization the ordinary
operation prevents stale live files, while `--keep-remote` remains an explicit
escape hatch for exceptional scopes. One planning model keeps preview and
execution aligned.

## Intentionally excluded

- Separate push and pull dry-run modes.
- Executing a previously displayed or persisted plan.
- Inferring renames from FTP metadata or file similarity.
- Automatically restoring a remote-only path during pull.
- Deleting any remote path outside the selected traversal scope.
- Uploading or pulling excluded paths.
- Retaining `-p` / `--prune-remote` as a redundant compatibility spelling.

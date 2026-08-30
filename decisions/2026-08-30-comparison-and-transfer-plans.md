# Comparison and transfer planning

Date: 2026-08-30

## Decision

`hlsync diff` is a read-only exploratory comparison over its selected scope.
Its default push perspective treats local existence as authoritative:
local-only paths are created remotely, changed files are replaced, and
remote-only paths are deleted. `-k` / `--keep-remote` changes remote-only
actions to retention. `--pull` reverses replacement direction but never
restores missing local paths or deletes remote paths.

`hlsync push --dry` is the exact execution preview. It uses push traversal—so a
bare invocation is recursive—along with the same selection, exclusions,
pruning policy, artifact-recovery projection, comparison plan, and ordered
operation derivation as a real push. It never executes recovery, upload,
replacement, directory creation, timestamp modification, or deletion.

Every transfer takes fresh snapshots and builds a new plan immediately before
mutation; displayed output is never an executable cached plan. Excluded local
paths are absent from the authoritative set. Remote exclusions are hard
synchronization boundaries and suppress operations beneath an excluded remote
directory. An explicitly selected remote-only directory is inventoried fully
so deletion can proceed deepest-first, unless a protected descendant makes the
ancestor undeletable.

## Rationale

Diff supports quick, shallow exploration, while dry push answers the distinct
question “what will this exact push execute?” Sharing ordered operation
derivation with execution prevents preview drift. Keeping dry artifact recovery
projective preserves read-only behavior without comparing against a server
state that real push would first repair.

## Intentionally excluded

- A pull dry-run mode; pull remains explicitly path-scoped and non-creative.
- Executing a previously displayed or persisted plan.
- Mutating interrupted-upload artifacts during a dry push.
- Inferring renames from FTP metadata or file similarity.
- Automatically restoring a remote-only path during pull.
- Deleting any remote path outside the selected traversal scope.
- Uploading or pulling excluded paths.
- Retaining `-p` / `--prune-remote` as a compatibility spelling.

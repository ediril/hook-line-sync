# Comparison and transfer planning

Date: 2026-08-30

## Decision

`hlsync diff` is a read-only exploratory comparison over its selected scope.
Its default push perspective treats local existence as authoritative for
creation and replacement: local-only paths are created remotely and changed
files are replaced when the source is newer, while remote-only paths are
retained. Deletion is opt-in:
`-p` / `--prune` on push, and on diff to preview it, deletes selected
remote-only paths, including remote copies of locally excluded files. `--pull` reverses replacement direction but never
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

Comparison entries preserve observed local and remote kinds separately from
their planned action. A locally excluded file can exist physically while being
absent from push authority; when pruning deletes it, the entry keeps its
excluded state so diff can show both the deletion and its reason. Presentation
derives presence from the observed kinds, exclusion from the state, and action
from the plan; exclusion and diagnostic markers never become transfer policy.

## Rationale

Diff supports quick, shallow exploration, while dry push answers the distinct
question “what will this exact push execute?” Sharing ordered operation
derivation with execution prevents preview drift. Keeping dry artifact recovery
projective preserves read-only behavior without comparing against a server
state that real push would first repair.

Keeping observed presence separate from authority prevents display concerns
from erasing facts needed to explain a planned deletion.

Deletion requires an explicit flag so a user who does not understand how
exclusions or scope interact cannot remove remote files by running a bare
push. Exclusions frequently come from `.gitignore`, which describes the Git
repository rather than the deployed site; deployed-only files such as site
verification pages are commonly Git-ignored.

## Intentionally excluded

- A pull dry-run mode; pull remains explicitly path-scoped and non-creative.
- Executing a previously displayed or persisted plan.
- Mutating interrupted-upload artifacts during a dry push.
- Inferring renames from FTP metadata or file similarity.
- Automatically restoring a remote-only path during pull.
- Deleting any remote path outside the selected traversal scope.
- Uploading or pulling excluded paths.
- Retaining `-k` / `--keep-remote` as a compatibility spelling.

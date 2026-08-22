# Compare and transfer plans

Date: 2026-08-21

## Decision

`hls compare`, with `hls cmp` as its shorthand, presents one deterministic
projection of the complete local and remote project trees. By default it shows
what `hls push` would do. `hls compare --pull` instead shows what `hls pull`
would do. It replaces the planned `hls list diff` and push/pull `--dry` modes.

Comparison derives upload, download, replace, delete, skip, conflict, and
unchanged actions from local-only, remote-only, changed, type-conflict, and
identical states. The local tree is authoritative for path existence. A
non-excluded remote path that is absent locally is skipped by default in both
directions. Running pull must not recreate a path that was intentionally
deleted locally.

Compare, push, and pull accept `--prune-remote`, with the shorthand `-p`, to
include deletion of remote-only paths. The long name states which side will
change even in pull mode. A real operation takes fresh complete snapshots and
builds its own transfer plan immediately before mutation; it does not execute a
previously displayed comparison.

A local-only path remains local during pull and is eligible for upload during
push. The overwrite policy for changed paths will be decided with comparison
states.

Compare, push, and pull accept one optional path selector. It is interpreted
relative to the current directory within the mapped local root and converted to
a project-relative POSIX pattern. A literal selects one file; `*` matches
within one path segment and `**` permits recursive matching. Shell wildcards
must be quoted to reach HLS unchanged. An omitted selector addresses the
complete project.

Selectors cannot be absolute, traverse with `..`, or escape the mapped root. A
selector that matches no non-excluded file on either side is an error rather
than a successful no-op. Selection never expands the configured exclusion
scope. `--prune-remote` deletes remote-only paths only inside the selected
scope.

The positional argument is reserved for the selector. An explicit project
override therefore uses `--project <name>`; otherwise the current directory
selects the project from its mapped root. When the current directory is inside
the selected project, selectors are relative to it. Otherwise an explicit
project override makes selectors relative to that project's local root.

Explicit selection does not override path-existence policy. Selecting a
remote-only file in pull mode still reports it as skipped rather than restoring
it locally.

## Rationale

A single comparison command avoids separate dry modes on mutation commands.
Push perspective is the default because the local tree is authoritative;
`--pull` makes the less common reverse direction explicit. Action-oriented
output answers what the corresponding command would do rather than requiring
the user to translate neutral states.

Fresh snapshots prevent a stale comparison from being treated as an executable
plan. Requiring `--prune-remote` separates evidence of deletion from
authorization to perform a destructive action.

## Consequences

- `hls compare` and `hls cmp` produce the same push-oriented output and make no
  changes.
- `--pull` changes the projection to pull behavior.
- Push and pull do not have a `--dry` option.
- Remote-only paths are reported and skipped by default on push and pull.
- `--prune-remote` / `-p` includes their deletion from the projected or actual
  remote operation.
- Excluded paths are absent from both snapshots and cannot enter a comparison,
  transfer, or delete plan.
- Pull does not restore a missing local path merely because it exists remotely.
- Independent remote additions remain untouched unless `--prune-remote` is
  explicitly supplied.
- Compare and transfer selection share one matcher and operate only on regular
  files. Required parent directories are plan mechanics, not selected content.

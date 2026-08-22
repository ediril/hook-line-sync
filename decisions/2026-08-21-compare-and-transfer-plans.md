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

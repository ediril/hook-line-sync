# Compare and transfer plans

Date: 2026-08-21

## Decision

`hls diff` presents one deterministic projection of the selected local and
remote scope. By default it shows what `hls push` would do. `hls diff --pull`
instead shows what `hls pull` would do. It replaces separate push/pull `--dry`
modes.

CLI output is a compact status view. Actions use `+`, `~`, `-`, and `?` for
creation, modification, deletion, and conflict. A skipped remote-only path uses
`r`; a skipped local-only path uses `l`. These side markers remain literal
under either perspective. Exclusions use `x`, unchanged files use `=`, and
directories that exist on both sides leave the status column blank because
entry equality does not establish content equality. A directory outside the
traversed depth adds a trailing `▸` indicator without replacing its
synchronization status. Exclusions can be hidden from the presentation with
`-i`/`--included-only`; they remain excluded from the synchronization plan.

Status lines use green, yellow, red, and magenta for actions and conflicts when
stdout is a terminal. Retained remote/local paths use dark/bright cyan,
untraversed directory details use dark-blue italics, unchanged files use the
normal terminal foreground, and gray is reserved for exclusions. Color is
disabled for redirected output and the `NO_COLOR` convention, with
`--color auto|always|never` as an explicit override.

Comparison derives upload, download, replace, delete, skip, conflict, and
unchanged actions from local-only, remote-only, changed, type-conflict, and
identical states. The local tree is authoritative for path existence. A
non-excluded remote path that is absent locally is skipped by default in both
directions. Running pull must not recreate a path that was intentionally
deleted locally.

Diff and push accept `--prune-remote`, with the shorthand `-p`, to include
deletion of remote-only paths. Pull rejects pruning. A real operation takes
fresh snapshots and
builds its own transfer plan immediately before mutation; it does not execute a
previously displayed comparison.

A local-only path remains local during pull and is eligible for upload during
push. Changed paths are replaced in the command's selected direction.

Diff, push, and pull accept zero or more path selectors. Each is interpreted
relative to the current directory within the mapped local root and converted to
a project-relative POSIX pattern. Multiple selectors form a deterministic
union, allowing shell-expanded arguments such as unquoted `*`. A selected
directory acts as a container: it includes its immediate contents, or its full
subtree with `--recursive`. Quote a wildcard when HLS should interpret it
unchanged. A literal selects one file, `*` matches within one path segment, and
`**` permits recursive matching.

Selectors cannot be absolute, traverse with `..`, or escape the mapped root. A
selection whose complete union matches no non-excluded file on either side is
an error rather than a successful no-op. Individual unmatched members do not
invalidate an otherwise matched union, because shells include directory names
when expanding `*`. Selection never expands the configured exclusion scope.
`--prune-remote` deletes remote-only paths only inside the selected scope.

Selectors are applied during snapshot traversal, before comparison. Local and
remote walkers enter only directories whose project-relative prefixes can
still satisfy the pattern. A single-segment `*` therefore scans only the
corresponding directory; recursive traversal occurs only where `**` or later
pattern segments can match descendants. With no operands, diff selects the
current directory's immediate contents. Bare push intentionally selects the
complete current subtree and is previewed by `hls diff -r`. Pull requires an
explicit operand; `hls pull .` selects the current directory, and `-r` extends
a directory selection through its subtree.

The positional arguments are reserved for selectors. An explicit project
override therefore uses `--project <name>`; otherwise the current directory
selects the project from its mapped root. When the current directory is inside
the selected project, selectors are relative to it. Otherwise an explicit
project override makes selectors relative to that project's local root.

Explicit selection does not override path-existence policy. Selecting a
remote-only file in pull mode still reports it as skipped rather than restoring
it locally.

## Rationale

A single comparison command avoids separate dry modes on mutation commands.
Local perspective is the default because the local tree is authoritative;
`--pull` makes the less common remote perspective explicit. Compact symbolic
output keeps large comparisons scannable while the shared internal plan retains
the concrete transfer actions.

Fresh snapshots prevent a stale comparison from being treated as an executable
plan. Requiring `--prune-remote` separates evidence of deletion from
authorization to perform a destructive action.

## Consequences

- `hls diff` produces push-oriented output by default and makes no changes.
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
- Compare and transfer selection share one matcher. Selected directories are
  synchronization containers, while required parent directories remain plan
  mechanics rather than independently selected content.

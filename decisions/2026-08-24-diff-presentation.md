# Diff presentation

Date: 2026-08-24

## Decision

Diff uses compact textual statuses: `+` create, `~` replace, `-` delete,
`?` conflict, `r` remote-only retained, `l` local-only retained, `=` unchanged
file, `x` excluded and absent remotely, and `!` excluded but present remotely.
Directories end in `/`; a directory present on both sides has no equality
marker because its entry says nothing about its contents. A trailing `▸` marks
a directory whose contents were not traversed.

List and diff show excluded entries by default. `-i`, `--inc`, or
`--included-only` hides them. Diff also shows unchanged entries by default.
Core synchronization status remains textual. Color respects `NO_COLOR` and
redirected output and has no command-line override. An `x` path uses excluded
gray or dark-blue styling. An excluded path that exists remotely uses a
burnt-orange `!`, preserving the distinction in non-color output as well.
`hlsync --legend` renders the current symbol and color reference without loading
a profile or connecting to FTPS.

A coherent scope is headed by one full project-relative anchor at column zero.
Its children begin one indent beneath it, including neutral directories that do
not reserve an invisible status column. Children use basenames and hierarchy
indentation; disjoint roots keep full paths to avoid ambiguity. Entries use
file-browser order at every level: directories first by name, then files by
name. Diff flushes results after each compared directory. `--paged` exits after
one directory and prints an exact stateless `--resume` command for the next
deterministic directory.

## Rationale

The display must distinguish action, retention, exclusion, and unknown depth at
a glance without claiming that an unvisited subtree is equal. Progressive and
stateless paging keep a slow FTPS comparison reviewable and interruptible.

## Intentionally excluded

- A separate `d` type column or an equality marker on two-sided directories.
- Repeating the complete parent path on every child.
- Using color as the only status signal.
- Persisting a paging session or cached comparison cursor.
- Displaying redundant direction and per-directory progress headings on stdout.
- Repeating the complete legend in each command's help.

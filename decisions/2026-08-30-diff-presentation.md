# Diff presentation

Date: 2026-08-30

## Decision

Diff uses compact textual statuses: `+` create, `~` replace, `-` delete,
`?` conflict, `r` remote-only retained, `l` local-only retained, `=` unchanged
file, `x` excluded and absent remotely, and `!` excluded but retained remotely.
Directories end in `/`; a two-sided directory has no equality marker because
its entry says nothing about its contents. A trailing `▸` marks a directory
whose contents were not traversed.

The default push view renders selected remote-only paths, including remote
copies of excluded local paths, as actionable `-` deletions. `--keep-remote`
uses `r` for ordinary remote-only paths; `--keep-remote --all` can show `!` for
retained excluded counterparts. `-i` hides neutral exclusions but never hides
an actionable deletion. `--pull` uses retained one-sided markers and does not
project deletion.

Bare diff does not enter child directories, but it projects bare push's
recursive deletion boundary. An immediate remote-only directory is therefore
shown as `- folder/ ▸`: deletion is actionable, while its contents remain
uninspected by diff. `-r` expands the subtree. An explicit shallow operand does
not inherit bare push recursion, so its unentered remote-only child is retained
and shown as `r folder/ ▸`.

Diff defaults to operational entries and omits unchanged, neutral excluded,
and untraversed entries. `-a` / `--all` restores the complete exploratory view.
Color respects `NO_COLOR` and redirected output and has no command-line
override. `hlsync --legend` renders the symbol and color reference without
loading a profile or connecting to FTPS.

A coherent scope is headed by one full profile-relative anchor at column zero.
Children use basenames and hierarchy indentation; disjoint roots keep full
paths. Entries use file-browser order at every level. Recursive output streams
each directory subtree after its parent. `--paged` exits after one directory and
prints an exact stateless `--resume` command for the next deterministic folder.

## Rationale

The display must distinguish action, retention, exclusion, and unknown depth
without relying on color. Showing default deletions directly makes diff an
honest preview of push; hiding actionable excluded-path deletions would make the
inspection filter unsafe.

## Intentionally excluded

- A separate `d` type column or equality marker on two-sided directories.
- Repeating the complete parent path on every child.
- Using color as the only status signal.
- Persisting a paging session or cached comparison cursor.
- Flattening different directory levels into one global sort.
- Repeating the complete legend in each command's help.

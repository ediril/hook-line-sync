# Selection and traversal scopes

Date: 2026-09-01

## Decision

With no operands, `list` and `diff` select the current directory's immediate
contents. Bare `push` selects the complete current subtree and is equivalent to
`push -r`. Pull requires at least one explicit operand.

A selected directory includes its immediate contents and adds descendants only
with `-r` / `--recursive`. `.` selects the current directory. Multiple paths or
wildcards form a deterministic union. A leading profile establishes its root as
a one-command virtual working directory. Paths cannot escape the profile root.

Traversal lists a directory, classifies each child, and only then schedules
eligible child directories. A directory excluded on the remote side is a hard
boundary: it is displayed but never entered, deleted, or otherwise mutated. A
locally excluded directory is also retained and not entered, because FTP cannot
delete a nonempty directory without traversing it. A later local inclusion that
may match a descendant permits the local walk needed to honor that inclusion;
remote boundaries cannot be pierced.

Locally excluded files remain file-level absences and may be deleted remotely
by ordinary push pruning. Included remote-only directories may be inventoried
and deleted recursively when they are inside recursive push scope. An explicitly
selected remote-only directory is likewise inventoried fully so FTP can delete
its contents deepest-first. A protected descendant retains its deletion
ancestors.

Bare diff remains shallow but marks an immediate included remote-only directory
as a collapsed recursive deletion because bare push will enter it. An explicit
shallow operand does not project implicit recursion. A directory outside
selected traversal depth is diagnostic only and is not authorization to create
or delete its contents.

## Rationale

Filtering before descent makes exclusions useful as scalability and safety
boundaries, while preserving recursive push for the included tree. Retaining a
locally excluded directory avoids pretending HLSync can prune it without doing
the very traversal the exclusion forbids. File-level pruning remains useful for
ordinary generated or unwanted files.

## Intentionally excluded

- Entering an excluded directory merely to inspect or prune it.
- Piercing a remote exclusion with a narrower child inclusion.
- Implicit recursion for `list`, `diff`, or an explicit directory operand.
- A bare pull operation.
- Walking ancestor directories merely to reach an exact selected directory.
- Persisting selection or traversal state between commands.
- Treating a visible untraversed directory as authorization to mutate it.
- Using `--keep-remote` to change traversal depth.

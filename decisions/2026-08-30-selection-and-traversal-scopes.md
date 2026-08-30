# Selection and traversal scopes

Date: 2026-08-30

## Decision

With no operands, `list` and `diff` select the current directory's immediate
contents. Bare `push` selects the complete current subtree and is equivalent to
`push -r`. Pull requires at least one explicit operand.

A selected directory includes its immediate contents and adds descendants only
with `-r` / `--recursive`. `.` selects the current directory. Multiple paths or
wildcards form a deterministic union. An unqualified command infers its profile
and relative scope from the current directory and fails outside mapped roots. A
leading profile establishes that profile root as a one-command virtual working
directory. Absolute paths, parent traversal, and paths escaping the root are
rejected.

Selection constrains traversal before comparison. A literal directory starts
at that directory; a wildcard starts at its narrowest fixed prefix. Default
push deletion never expands traversal depth: a shallow directory selection can
delete immediate remote-only children but does not enter child directories.
Recursive push and push-oriented diff may enter selected remote-only or excluded
subtrees because their contents are eligible for deletion. `--keep-remote`
changes deletion policy, not selection depth. Bare push remains recursive by
definition.

An immediate directory outside selected traversal depth is a diagnostic
boundary, not an executable action. It may be displayed with `▸`, but transfer
does not create, replace, or delete its contents. A selected directory itself
may still be created as a required parent of selected files.

## Rationale

Shallow explicit scopes keep inspection predictable and bound deletion to what
the user named. Recursive current-tree push remains convenient for complete
deployment. Selecting before traversal avoids unrelated remote work, while a
separate retention option avoids confusing mutation policy with recursion.

## Intentionally excluded

- Implicit recursion for `list`, `diff`, or an explicit directory operand.
- A bare pull operation.
- Walking ancestor directories merely to reach an exact selected directory.
- Letting selection broaden configured synchronization rules.
- Persisting selection or traversal state between commands.
- Falling back to a previously selected profile outside mapped roots.
- Treating a visible untraversed directory as authorization to mutate it.
- Using `--keep-remote` to change traversal depth.
- Using a leading profile's virtual root as `map`'s implicit local root.

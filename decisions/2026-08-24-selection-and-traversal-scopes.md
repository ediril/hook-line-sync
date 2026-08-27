# Selection and traversal scopes

Date: 2026-08-24

## Decision

With no operands, `list` and `diff` select the current directory's immediate
contents. Bare `push` deliberately selects the complete current subtree and is
equivalent to `push -r`. Pull requires at least one explicit operand.

A selected directory is a container: it includes its immediate contents and
adds descendants only with `-r` / `--recursive`. `.` explicitly selects the
current directory. Multiple path or wildcard operands form a deterministic
union. Operands are relative to the current directory inside the mapped root,
or to the selected profile's root when used outside it with `--project`.
Absolute paths, parent traversal, and paths escaping the root are rejected.
A union that matches no eligible path on either side is an error; one unmatched
operand does not invalidate an otherwise matched union.

Selection constrains traversal before comparison. A literal directory starts
directly at that directory; a wildcard starts at its narrowest fixed prefix.
Local traversal leads the default comparison, and the corresponding remote
directory is queried after local scope is known. Remote-only subtrees are not
entered unless explicit pruning needs them. Excluded directories are not
entered unless a narrower inclusion can match beneath them.

## Rationale

Shallow explicit scopes make ordinary inspection predictable and avoid needless
FTP listings. Recursive transfer of the current tree remains convenient for the
primary deployment operation, while pull requires the user to name what may be
overwritten locally.

## Intentionally excluded

- Implicit recursion for `list`, `diff`, or an explicit directory operand.
- A bare pull operation.
- Walking ancestor directories merely to reach an exact selected directory.
- Letting selection broaden configured synchronization rules.
- Persisting selection or traversal state between commands.

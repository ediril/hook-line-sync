# Selection and traversal scopes

Date: 2026-08-24

## Decision

With no operands, `list` and `diff` select the current directory's immediate
contents. Bare `push` deliberately selects the complete current subtree and is
equivalent to `push -r`. Pull requires at least one explicit operand.

A selected directory is a container: it includes its immediate contents and
adds descendants only with `-r` / `--recursive`. `.` explicitly selects the
current directory. Multiple path or wildcard operands form a deterministic
union. An unqualified command infers its profile and relative scope from the
current directory and fails outside every mapped root. A leading profile, such
as `hlsync staging diff`, is an explicit one-command override whose virtual
working directory is that profile's root; it does not change the process
working directory or persist selection. Absolute paths, parent traversal, and
paths escaping the root are rejected.
A union that matches no eligible path on either side is an error; one unmatched
operand does not invalidate an otherwise matched union.

Selection constrains traversal before comparison. A literal directory starts
directly at that directory; a wildcard starts at its narrowest fixed prefix.
Local traversal leads the default comparison, and the corresponding remote
directory is queried after local scope is known. Remote-only subtrees are not
entered unless explicit pruning needs them. Excluded directories are not
entered unless a narrower inclusion can match beneath them or push pruning is
authorized within a recursive scope. `-p` authorizes deletion but never expands
traversal depth; `-r` controls recursion independently. Bare push is already a
recursive scope by definition.

An immediate directory outside the selected traversal depth is a diagnostic
boundary, not an executable transfer action. It may be displayed with `▸`, but
push and pull do not create, replace, or delete it. A selected directory itself
may still be created as a required parent of selected files.

## Rationale

Shallow explicit scopes make ordinary inspection predictable and avoid needless
FTP listings. Recursive transfer of the current tree remains convenient for the
primary deployment operation, while pull requires the user to name what may be
overwritten locally. Requiring either mapped-directory context or an explicit
per-command profile prevents hidden state from directing work at an unintended
project.

## Intentionally excluded

- Implicit recursion for `list`, `diff`, or an explicit directory operand.
- A bare pull operation.
- Walking ancestor directories merely to reach an exact selected directory.
- Letting selection broaden configured synchronization rules.
- Persisting selection or traversal state between commands.
- Falling back to a previously selected profile outside mapped roots.
- Treating a visible untraversed directory as authorization to mutate it.
- Treating pruning authorization as recursive selection.
- Applying the virtual working directory to `map`, whose purpose is to map the
  real current directory.

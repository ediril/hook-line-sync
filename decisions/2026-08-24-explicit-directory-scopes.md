# Current and explicit directory scopes

## Decision

No-argument `diff`, `push`, and `pull` select the current directory's immediate
contents. `-r` or `--recursive` additionally selects every descendant. When one
of those commands receives an explicit directory operand, the directory is a
synchronization container with the same shallow-by-default behavior.

An existing directory that is selected but not traversed is always emitted by
`diff` with a collapsed `▸ d` state, even without `--all`. This state means only
that the directory entry exists on both sides; HLS makes no claim about its
contents. Terminal output renders it dark blue and italic. Recursive traversal
replaces the collapsed state with comparisons from inside that directory.

`list` uses the same operand expansion but omits the selected container from
display, matching normal directory-listing expectations. Its no-argument scope
remains the current directory's immediate contents.

## Rationale

Directory operands should not require spelling `directory/*`, and a scoped diff
must describe the corresponding push or pull exactly. Making no-argument
commands current-directory-scoped keeps accidental transfers bounded; a full
project operation remains explicit as `hls diff -r`, `hls push -r`, or
`hls pull -r` from the mapped root.

Wildcard operands use the same rule: any matched directory acts as a container.
This keeps quoted patterns and shell-expanded directory arguments consistent.

## Intentionally unchanged

- Exclusions remain local policy and are applied before remote traversal.
- Remote pruning remains push-only and explicitly authorized.
- No paging or selector state is persisted.

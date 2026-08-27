# Current and explicit directory scopes

## Decision

No-argument `diff`, `push`, and `pull` select the current directory's immediate
contents. `-r` or `--recursive` additionally selects every descendant. When one
of those commands receives an explicit directory operand, the directory is a
synchronization container with the same shallow-by-default behavior.

A directory that is selected but not traversed is always emitted by `diff`.
Its synchronization status remains independent: for example, `+ cache/ ▸` is
a new local directory and `r cache/ ▸` is a retained remote-only directory.
The dark-blue italic trailing `▸` means HLS makes no claim about the directory's
contents.
Recursive traversal removes that suffix and prints the comparisons from inside
the directory.

`list` uses the same operand expansion but omits the selected container from
display, matching normal directory-listing expectations. Its no-argument scope
remains the current directory's immediate contents.

Diff shows an unchanged selected container with a blank status column because
equality of the directory entry says nothing about equality of its contents.
This keeps the selected directory visible without making a content-equality
claim. A one-sided, excluded, or otherwise actionable container retains its
meaningful status marker.

Other directories that exist on both sides use a blank status column rather
than `=` for the same reason. Their trailing `/`, directory color, and optional
`▸` traversal marker remain visible. One-sided and excluded directories retain
their meaningful status markers.

Diff presents one full project-relative path as the anchor for each coherent
traversal root rather than rendering every ancestor as a separate row. Its
immediate children use basenames and one level of indentation, with each deeper
level adding another indentation level. This is presentation-only: selectors,
comparison entries, diagnostics, resume cursors, and transfer plans retain full
project-relative paths. Disjoint multi-root selections also retain full paths
in the display so identical basenames cannot become ambiguous.

## Rationale

Directory operands should not require spelling `directory/*`, and a scoped diff
must describe the corresponding explicit push or pull exactly. Explicit
directory operands remain shallow by default. Bare push is the deliberate
exception: it selects the complete current subtree and is equivalent to
`hlsync push -r`; its preview is `hlsync diff -r`. Bare diff remains shallow. Pull has
no bare scope: it requires an explicit operand, with `.` available to select the
current directory.

Wildcard operands use the same rule: any matched directory acts as a container.
This keeps quoted patterns and shell-expanded directory arguments consistent.
Traversal starts at the narrowest fixed directory implied by the selection. A
literal directory such as `var` is listed directly on both sides; HLS does not
list `.` first merely to discover it. A wildcard starts at its fixed prefix, or
at the current scope when it has no narrower prefix.

## Intentionally unchanged

- Exclusions remain local policy and are applied before remote traversal.
- Remote pruning remains push-only and explicitly authorized.
- No paging or selector state is persisted.
- A failed direct remote-directory lookup is provisionally treated as a missing
  destination directory. Push remains responsible for reporting and skipping
  any path the server later refuses to create or write.

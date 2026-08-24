# Explicit directory scopes

## Decision

No-argument `diff`, `push`, and `pull` retain full-project recursive scope.
When one of those commands receives an explicit directory operand, the
directory is a synchronization container: the directory and its immediate
contents enter the plan. `-r` or `--recursive` additionally selects every
descendant.

`list` uses the same operand expansion but omits the selected container from
display, matching normal directory-listing expectations. Its no-argument scope
remains the current directory's immediate contents.

## Rationale

Directory operands should not require spelling `directory/*`, and a scoped diff
must describe the corresponding push or pull exactly. Keeping the no-argument
transfer scope unchanged preserves the established full-project workflow.

Wildcard operands use the same rule: any matched directory acts as a container.
This keeps quoted patterns and shell-expanded directory arguments consistent.

## Intentionally unchanged

- Exclusions remain local policy and are applied before remote traversal.
- Remote pruning remains push-only and explicitly authorized.
- No paging or selector state is persisted.

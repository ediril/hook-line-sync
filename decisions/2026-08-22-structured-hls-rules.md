# Structured HLS synchronization rules

Date: 2026-08-22

## Decision

Replace raw Gitignore strings with ordered structured rules containing a stable
positive integer ID, an explicit `include` or `exclude` action, and a normalized
project-relative HLS pattern. Configuration schema version 7 stores the next ID
for each project and intentionally provides no compatibility path for schema 6.

HLS pattern semantics are independent of Gitignore:

- Patterns are rooted at the directory where the command is run.
- `*` matches within one path segment.
- A complete `**` segment matches across directory levels.
- A literal directory is normalized to a recursive `directory/**` pattern.
- Literal files remain exact project-relative paths.
- `?`, bracket patterns, partial-segment `**`, absolute paths, and parent
  traversal are rejected.

Rules remain deterministic and ordered; the last rule matching a path wins and
unmatched paths are included by default. Adding an identical normalized pattern
removes its earlier rule before appending the new action. If the remaining
policy already produces the requested state, HLS omits the replacement instead.
This cleanup is limited to cases HLS can prove: concrete paths, or an inclusion
when no exclusions remain. Other overlaps are preserved rather than simplified
symbolically.

## Management and diagnostics

`hls rules` groups the complete policy by its nearest literal folder and sorts
expressions by name. Patterns without a fixed folder appear under `Everywhere`.
Stable IDs remain visible because higher matching IDs still take precedence,
even though the inspection view is organized for readability rather than
evaluation order. `hls rules remove <id>` removes a specific persisted rule.
`hls include` and `hls exclude` without operands provide filtered grouped views
with the same IDs. `hls list` is the materialized local-tree view of the policy.

## Consequences

- Users do not need to understand `!`, leading-slash anchoring, or Gitignore
  basename rules.
- Rule IDs remain stable across removals; they are not renumbered or reused.
- Schema 6 projects must be recreated rather than silently reinterpreted.
- Local and FTPS traversal use the same rule evaluator. Traversal may descend an
  excluded directory when an inclusion could match below it, preserving narrow
  exceptions without exposing excluded paths to transfer operations.
- Matching is currently linear in the number of rules per visited path. Literal
  and wildcard indexing remains a measured scalability task in `TODO.md`.

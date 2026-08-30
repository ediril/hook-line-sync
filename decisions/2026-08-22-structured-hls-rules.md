# Structured synchronization rules

Date: 2026-08-22

## Decision

Synchronization policy is an ordered list of structured rules. Each rule has a
stable positive integer ID, an explicit `include` or `exclude` action, and a
normalized profile-relative pattern. The last matching rule wins; an unmatched
path is included.

Patterns are rooted where the command is run. `*` matches within one path
segment, and a complete `**` segment matches across directory levels. Literal
directories normalize to recursive `directory/**` rules and literal files to
exact paths. Empty patterns, absolute paths, parent traversal, `?`, bracket
patterns, and partial-segment `**` are rejected.

Adding the same normalized pattern removes its prior rule before evaluating
the requested action. Further cleanup occurs only where equivalence can be
proved without changing the effective policy. Rule inspection may group and
sort for readability, but evaluation remains ordered by stable ID.

## Rationale

Explicit actions and deliberately small wildcard semantics avoid requiring
users to reason in Gitignore syntax. Stable IDs make rules removable even when
the displayed view is organized by folder rather than evaluation order.

## Intentionally excluded

- Gitignore negation, basename-at-any-depth rules, and its complete pattern
  language.
- Renumbering or reusing IDs after removal.
- Symbolically simplifying overlapping wildcard rules when equivalence is not
  provable.
- Treating presentation order as evaluation order.

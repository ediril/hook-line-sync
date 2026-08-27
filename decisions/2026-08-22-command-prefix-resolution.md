# Command prefix resolution

Date: 2026-08-22

## Decision

Command names accept the shortest unique prefix, while an exact command name
always wins. When a prefix matches multiple commands, an interactive terminal
lists the candidates and asks the user to choose; non-interactive use fails and
lists the same candidates.

Compatibility spelling `ls` continues to resolve to `list` without appearing
in top-level help. `inc` and `exc` need no aliases because they are unique
prefixes of `include` and `exclude`.

## Rationale

Prefix resolution provides convenient shorthand without maintaining parallel
aliases. Explicit ambiguity handling prevents the meaning of an existing
abbreviation from silently changing when a command is added.

## Intentionally excluded

- Resolving ambiguity by registration order or an arbitrary first match.
- Prompting when standard input is not interactive.
- Advertising compatibility spellings in the primary command menu.

# Command prefix resolution

Date: 2026-08-30

## Decision

Command names accept the shortest unique prefix, while an exact command name
always wins. An ambiguous prefix prompts for a numbered choice in an
interactive terminal and fails with the same candidates when non-interactive.

Compatibility spellings `ls` and `lsr` resolve to local and remote `list`
invocations without requiring separate implementations. Synchronization policy
changes belong to `rules`; `exclude`, `include`, `exc`, and `inc` are not
top-level commands.

## Rationale

Unique prefixes provide shorthand without parallel command implementations.
Explicit ambiguity handling prevents an abbreviation from silently changing
meaning when commands are added. Keeping policy under one command gives rule
inspection, addition, and removal one discoverable home.

## Intentionally excluded

- Resolving ambiguity by registration order or an arbitrary first match.
- Prompting when standard input is not interactive.
- Restoring standalone commands for individual rule actions.
- Treating compatibility spellings as separate behavior paths.

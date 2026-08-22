# Command prefixes and ordered synchronization rules

Date: 2026-08-22

## Decision

All command names accept the shortest unambiguous prefix. Exact command names
and the established `ls`, `lsl`, `lsr`, and `cmp` spellings take precedence.
Ambiguous prefixes fail and name every candidate rather than choosing based on
registration order.

`hls map` only maps the current directory. `hls exclude` and `hls include`,
which naturally permit `hls exc` and `hls inc`, append comma-separated rules to
the inferred project's persistent synchronization scope. `--project <name>` is
the explicit override. Rules use gitignore matching and retain insertion order;
a later include or exclude therefore overrides an earlier matching rule.

Walkers do not expose excluded entries. When a later inclusion can match below
an excluded directory, local and remote walkers traverse only the potentially
relevant excluded branch so the override is reachable. File selectors continue
to prune traversal independently, and both conditions must permit descent.

## Rationale

Exclusions describe evolving project policy rather than the one-time act of
mapping a root. Separate commands allow that policy to change without remapping
or editing configuration files. Ordered overrides support a broad exclusion
with narrow durable exceptions.

Unique-prefix resolution provides predictable shorthand without maintaining a
growing alias table. Rejecting ambiguity prevents command meaning from silently
changing when a new command is added.

## Consequences

- Stored `exclusions` remains an array in schema version 6, but order is now
  semantically significant and `!` entries represent inclusion rules.
- Existing configurations remain valid; their previously persisted order is
  retained.
- Direct command patterns cannot be empty, contain `..`, or begin with `!`.
- Inclusion patterns with an indeterminate wildcard prefix may require scanning
  more excluded directories to preserve correctness, but never broaden the
  resulting synchronization scope.

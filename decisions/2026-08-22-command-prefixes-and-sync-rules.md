# Command prefixes and ordered synchronization rules

Date: 2026-08-22

## Decision

All command names accept the shortest unambiguous prefix. Exact command names
and the established `lsl` and `lsr` spellings take precedence. `ls` and `cmp`
are resolver-level compatibility spellings: they remain functional but are not
registered with the argument parser and therefore do not appear in the help
menu. Ambiguous prefixes fail and name every candidate rather than choosing
based on registration order.

`hls map` only maps the current directory. `hls exclude` and `hls include`,
which naturally permit `hls exc` and `hls inc`, append one or more pattern
arguments to the inferred project's persistent synchronization scope. Each
argument may also contain comma-separated patterns, so quoted HLS wildcards and
unquoted shell-expanded argument lists are both accepted. `--project <name>` is
the explicit override. Rules use gitignore matching and retain insertion order;
a later include or exclude therefore overrides an earlier matching rule.

Operational walkers do not expose excluded entries. When a later inclusion can
match below an excluded directory, local and remote walkers traverse only the
potentially relevant excluded branch so the override is reachable. File
selectors continue to prune traversal independently, and both conditions must
permit descent.

Compare requests diagnostic snapshots that expose excluded files with an
explicit exclusion flag and traverse excluded directories needed to enumerate
them. Comparison converts those entries to a neutral `excluded` action, shown
with a gray `·` marker. Push, pull, tree listings, and pruning continue to use
operational snapshots in which excluded paths are absent.

## Rationale

Exclusions describe evolving project policy rather than the one-time act of
mapping a root. Separate commands allow that policy to change without remapping
or editing configuration files. Ordered overrides support a broad exclusion
with narrow durable exceptions.

Unique-prefix resolution provides predictable shorthand without maintaining a
growing alias table. Rejecting ambiguity prevents command meaning from silently
changing when a new command is added.

Compare, push, pull, exclude, and include register one shared pattern-operand
grammar. It accepts shell-expanded argument lists, preserves quoted wildcards,
and flattens comma-separated groups before command-specific validation. The
shared declaration controls whether operands are optional or required; commands
do not independently implement argument cardinality or normalization.

Exclude and include make their operands optional for a complementary query
mode. With no operands, or with explicit `--list`, they enumerate effectively
excluded or included regular files beneath the mapped local root. Query mode
uses a local diagnostic snapshot and never opens an FTPS connection. Supplying
patterns with `--list` is rejected rather than guessing between query and
mutation.

Persistent rule operands distinguish literal paths from wildcard rules. A
literal is resolved from the current directory and stored as an anchored
project-relative Gitignore rule. A pattern containing `*`, `?`, or `[` remains
a Gitignore wildcard evaluated against the project root. Consequently, shell
expansion selects the exact paths the shell supplied, while quoting preserves a
wildcard for HLS to apply recursively according to Gitignore semantics.

## Consequences

- Stored `exclusions` remains an array in schema version 6, but order is now
  semantically significant and `!` entries represent inclusion rules.
- Stored rules are always compiled verbatim as Gitignore entries. Existing bare
  patterns therefore retain standard basename-at-any-depth behavior; HLS does
  not reinterpret them based on the version that wrote them.
- Direct command patterns cannot be empty, contain `..`, or begin with `!`.
- Commas delimit operand groups consistently and therefore cannot address a
  literal filename containing a comma.
- Inclusion patterns with an indeterminate wildcard prefix may require scanning
  more excluded directories to preserve correctness, but never broaden the
  resulting synchronization scope.
- A complete compare inspects excluded directories to report their files and
  can therefore do more local and remote I/O than a transfer. Selector-limited
  compares retain selector-first traversal pruning.

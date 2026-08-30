# Synchronization rules

Date: 2026-08-30

## Decision

Synchronization policy has two ordered layers: global rules from
`~/.hlsync/rules.json`, followed by rules stored in the active profile. The
last matching rule across those layers wins, so a profile rule may override a
global rule. An unmatched path is included.

The global file has its own version and ordered rules. It is seeded once with
conservative exclusions for Git, Subversion, and Mercurial metadata plus
`.DS_Store`, `Thumbs.db`, and `desktop.ini` at any depth. Once created, the file
belongs to the user; later releases do not merge or restore defaults
automatically.

`include` and `exclude` operate on the active profile by default. `-g` /
`--global` selects the global layer and works without an active profile.
Global operands are reusable patterns rooted at each profile root; a trailing
slash denotes a complete directory tree. `rules` displays global and profile
layers together, while `rules -g` inspects or removes only global rules.

Stored IDs are positive integers scoped to their separate files and calculated
as the highest current ID plus one. Deleting the highest rule permits its ID to
be reused; deleting every rule restarts numbering at one. No allocation counter
is persisted. CLI identifiers expose scope: profile rules use the numeric form
(`3`) and global rules use a `g` prefix (`g3`). Rule output and update output
always show the copyable scoped form, and removal requires the form appropriate
to the selected scope. Effective-policy assembly reindexes rules only
transiently for matching and does not alter either persisted sequence.

Each stored rule has an explicit `include` or `exclude` action and a normalized
profile-relative pattern. `*` matches within one path segment, and a complete
`**` segment matches across directory levels. Empty patterns, absolute paths,
parent traversal, `?`, bracket patterns, and partial-segment `**` are rejected.

Adding the same normalized pattern removes its prior rule before evaluating
the requested action. Further cleanup occurs only where equivalence can be
proved without changing the effective layered policy. Rule inspection may
group and sort for readability, but evaluation remains ordered.

## Rationale

A user-owned global layer removes repetitive setup without hiding policy in
code. Applying profile rules last preserves the ability to make an explicit
deployment-specific exception. Conservative defaults avoid silently omitting
dependencies or application data whose deployability varies by profile.
Scoped CLI identifiers prevent visually identical IDs from implying that the
separate stores share a removal namespace, while retaining the simple integer
representation used by ordering and matching. IDs exist only to select a
current rule for removal, so preserving allocation history would add state
without protecting a real reference.

## Intentionally excluded

- Default exclusions for `vendor`, `node_modules`, `.env`, lockfiles, tests,
  logs, temporary extensions, or other potentially deployable content.
- Automatically merging new defaults into an existing global rules file.
- Requiring an active profile for global rule management.
- A single shared persisted ID sequence across global and profile files.
- Accepting numeric global IDs or `g`-prefixed profile IDs as aliases.
- Persisting a next-ID counter or guaranteeing that deleted IDs are never
  reused.
- Gitignore negation, basename-at-any-depth rules, and its complete pattern
  language.
- Renumbering surviving rules after removal.
- Symbolically simplifying overlapping wildcard rules when equivalence is not
  provable.
- Treating presentation order as evaluation order.

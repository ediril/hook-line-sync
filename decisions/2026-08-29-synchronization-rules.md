# Synchronization rules

Date: 2026-08-29

## Decision

Synchronization policy has two ordered layers: global rules from
`~/.hlsync/rules.json`, followed by rules stored in the active profile. The
last matching rule across those layers wins, so a profile rule may override a
global rule. An unmatched path is included.

The global file has its own version, stable rule IDs, and next-ID counter. It
is seeded once with conservative exclusions for Git, Subversion, and Mercurial
metadata plus `.DS_Store`, `Thumbs.db`, and `desktop.ini` at any depth. Once
created, the file belongs to the user; later releases do not merge or restore
defaults automatically.

`include` and `exclude` operate on the active profile by default. `-g` /
`--global` selects the global layer and works without an active profile.
Global operands are reusable patterns rooted at each profile root; a trailing
slash denotes a complete directory tree. `rules` displays global and profile
layers together, while `rules -g` inspects or removes only global rules. Rule
IDs are scoped to their storage layer and are reindexed only in the transient
effective policy used for matching.

Each stored rule has a stable positive integer ID, an explicit `include` or
`exclude` action, and a normalized profile-relative pattern. `*` matches within
one path segment, and a complete `**` segment matches across directory levels.
Empty patterns, absolute paths, parent traversal, `?`, bracket patterns, and
partial-segment `**` are rejected.

Adding the same normalized pattern removes its prior rule before evaluating
the requested action. Further cleanup occurs only where equivalence can be
proved without changing the effective layered policy. Rule inspection may
group and sort for readability, but evaluation remains ordered.

## Rationale

A user-owned global layer removes repetitive setup without hiding policy in
code. Applying profile rules last preserves the ability to make an explicit
deployment-specific exception. Conservative defaults avoid silently omitting
dependencies or application data whose deployability varies by project.
Separate persistence keeps global and profile rule IDs stable while a shared
reconciliation mechanism prevents their behavior from drifting.

## Intentionally excluded

- Default exclusions for `vendor`, `node_modules`, `.env`, lockfiles, tests,
  logs, temporary extensions, or other potentially deployable content.
- Automatically merging new defaults into an existing global rules file.
- Requiring an active profile for global rule management.
- A single shared ID namespace across global and profile files.
- Gitignore negation, basename-at-any-depth rules, and its complete pattern
  language.
- Renumbering or reusing stored IDs after removal.
- Symbolically simplifying overlapping wildcard rules when equivalence is not
  provable.
- Treating presentation order as evaluation order.

# Changelog

## 0.8.30.3 — 2026-08-30

### Changed

- Remove persisted `next_rule_id` counters from global and profile
  configuration; new disposable IDs now follow the highest current ID.

## 0.8.30.2 — 2026-08-30

### Changed

- Display and accept global rule IDs as `g1`, `g2`, and so on, keeping them
  unambiguous beside numeric profile rule IDs.

## 0.8.30.1 — 2026-08-30

### Changed

- Recover interrupted-upload artifacts while traversing selected push
  directories instead of recursively scanning the remote scope before the
  comparison.

## 0.8.29.16 — 2026-08-29

### Added

- Seed an editable `~/.hlsync/rules.json` with conservative global metadata
  exclusions and add `-g` / `--global` rule management that works outside
  mapped profiles.

### Changed

- Evaluate global rules before profile rules, allow profile-specific overrides,
  and show both layers together through `hlsync rules`.

## 0.8.29.15 — 2026-08-29

### Changed

- Rename the Python package from `hls` to `hlsync`, move configuration from
  `~/.hls` to `~/.hlsync`, and rename the persisted `projects` collection to
  `profiles` in configuration version 8.
- Rename HLSync-owned staging artifacts from `.hls-*` to `.hlsync-*` without
  compatibility aliases or migration behavior.

## 0.8.29.14 — 2026-08-29

### Changed

- Consolidate obsolete profile-selection and mapping decisions into a current
  profile model, and replace the traversal decision with a newly dated version
  that reflects explicit local and remote root editing.

## 0.8.29.13 — 2026-08-29

### Changed

- Rename the profile creation command from `add` to `create`.
- Use “profile” consistently for configured deployment targets in CLI output,
  help, errors, and current documentation.
- Expand `map` to update a profile's local root, remote root, or both through a
  validated old → new confirmation that defaults to no.

## 0.8.29.12 — 2026-08-29

### Changed

- Clarify the alternate local-root prompt shown by `hlsync add`.

## 0.8.29.11 — 2026-08-29

### Changed

- Require every newly added profile to have a local mapping: `--local-root`
  supplies it directly, while declining the offered current directory now
  prompts for another local folder.

## 0.8.29.10 — 2026-08-29

### Changed

- Add concise profile-prefix guidance when `hlsync profile` finds no active
  profile.

## 0.8.29.9 — 2026-08-29

### Changed

- Make `hlsync profile` report `No active profile.` outside mapped roots
  instead of treating the absence of an active profile as an error.

## 0.8.29.8 — 2026-08-29

### Added

- Add `hlsync root [PROFILE]` to print only the canonical mapped local root for
  shell composition such as `cd "$(hlsync root staging)"`.

## 0.8.29.7 — 2026-08-29

### Changed

- Clarify that mapped-directory inference is the normal workflow and a leading
  profile is a non-persistent one-command override.
- Make outside-root failures suggest the explicit `hlsync PROFILE COMMAND`
  form instead of referring to an unmapped project without guidance.

## 0.8.29.6 — 2026-08-29

### Changed

- Make `diff` show only actions, retained one-sided paths, and conflicts by
  default; add `-a`/`--all` for the previous complete exploratory view.
- Emit compact-mode directory ancestors only when they contain a visible
  result, preserving progressive hierarchy without empty directory noise.

## 0.8.29.5 — 2026-08-29

### Fixed

- Render recursive local listings as an indented tree with each directory name
  shown once instead of repeating project-relative parent prefixes on children.
- Preserve directory-first ordering when a filtered selection requires HLSync
  to synthesize an omitted ancestor for display.

## 0.8.29.4 — 2026-08-29

### Fixed

- Keep recursively diffed directory contents directly beneath their parent
  instead of printing root files between a directory and its children.

## 0.8.29.3 — 2026-08-29

### Changed

- Replaced command-level `--project` options with a leading profile syntax,
  such as `hlsync dengine list`, which uses the mapped local root as an
  explicit virtual working directory for path-oriented commands.
- Preserve the selected profile in stateless paged-diff resume commands.

## 0.8.29.2 — 2026-08-29

### Changed

- Report explicitly enabled scope, visibility, perspective, paging, and pruning
  options in `list`, `diff`, `push`, and `pull` output.

## 0.8.29.1 — 2026-08-29

### Added

- Added a v2 `llms.txt` project summary with curated links to the README,
  changelog, license, source, and work queue.
- Added explicit search robots directives, Open Graph locale, author metadata,
  SoftwareApplication JSON-LD, and `rel="describedby"` discovery for llms.txt.

## 0.8.28.22 — 2026-08-28

### Added

- Completed the website favicon set from the existing hook mark with an SVG
  primary icon, 32-pixel PNG fallback, multi-size root ICO, and 180-pixel Apple
  touch icon.

## 0.8.28.21 — 2026-08-28

### Added

- Added a branded 1200-by-630 social preview image matching the website's
  terminal design.
- Added Open Graph, Twitter large-image card, canonical URL, image dimensions,
  and accessible image-description metadata using absolute request-host URLs.

## 0.8.28.20 — 2026-08-28

### Changed

- Added a user-focused README introduction for developers who want a safer FTPS
  workflow without adopting a full deployment stack.
- Made the local-source-of-truth assumption explicit before installation.

## 0.8.28.19 — 2026-08-28

### Changed

- Recommended `uv tool install hook-line-sync` for an isolated CLI installation
  and simplified the alternative to `pip install hook-line-sync`.

## 0.8.28.18 — 2026-08-28

### Fixed

- Made PyPI the sole user-facing installation path in the README; cloning the
  repository remains unnecessary outside development.

## 0.8.28.17 — 2026-08-28

### Changed

- Reordered the README as a user-first guide and moved development setup,
  package internals, work tracking, and release maintenance to the end.
- Added current source-checkout installation instructions.

## 0.8.28.16 — 2026-08-28

### Changed

- Indented `Nothing to push` and `Nothing to pull` like streamed transfer
  operations.
- Added the unchanged included-file count to an empty push result, scoped to
  exactly what the command inspected.

## 0.8.28.15 — 2026-08-28

### Fixed

- Kept `-p` as deletion authorization only; it no longer enables excluded-tree
  traversal unless the push scope is recursive through `-r` or bare push.
- Applied the same depth boundary to diff projection so shallow `diff -p` and
  shallow `push -p` remain aligned.

## 0.8.28.14 — 2026-08-28

### Changed

- Treated excluded local paths as absent for push authority: remote copies are
  retained with a `-p` hint by default and deleted when pruning is authorized.
- Separated excluded-entry visibility from excluded-directory traversal, so an
  ordinary push can detect retained excluded paths without recursively scanning
  their subtrees; recursive pruning traverses them for safe deepest-first
  deletion.

## 0.8.28.13 — 2026-08-28

### Changed

- Collapsed the post-push remote-only report to one `-p` pruning hint instead
  of enumerating paths already available through `diff`.

## 0.8.28.12 — 2026-08-28

### Changed

- Replaced empty `Pushing changes` or `Pulling changes` phases with a direct
  `Nothing to push` or `Nothing to pull` result.
- Grouped retained remote-only paths after push and added a push-only hint that
  `-p` authorizes their deletion.

## 0.8.28.11 — 2026-08-28

### Changed

- Aligned streamed transfer paths with fixed-width operation labels for easier
  scanning without relying on terminal-specific tab stops.

## 0.8.28.10 — 2026-08-28

### Changed

- Streamed `Adding`, `Updating`, `Creating`, and `Deleting` path updates as
  transfer operations begin, so long transfers identify the active path.
- Replaced the successful transfer's internal comparison table with a compact
  change count while continuing to report deliberately retained remote-only
  paths.

## 0.8.28.9 — 2026-08-28

### Changed

- Reworked the README into a shorter current-user guide covering setup,
  selection, rules, listing, diff, transfer safety, and release maintenance.
- Documented why pushes use verified staging files instead of writing directly
  over live destinations, including automatic interrupted-transfer recovery.

## 0.8.28.8 — 2026-08-28

### Fixed

- Added scoped pre-push recovery for HLSync-owned interrupted-transfer files:
  abandoned uploads are removed, obsolete backups are removed, and a sole
  backup is restored when its destination is missing.
- Kept internal artifact recovery independent of `--prune-remote`; ordinary
  remote-only files remain protected.

## 0.8.28.7 — 2026-08-28

### Fixed

- Accepted successful server-specific MFMT replies such as `213 UTIME OK`
  instead of requiring one response phrase.
- Added independent MDTM read-back verification before installing an upload and
  cleanup of staged files when size, timestamp, or local-source validation
  fails.

## 0.8.28.6 — 2026-08-28

### Changed

- Replaced internal “building/executing plan” progress with “Comparing local
  and remote files” followed by “Pushing changes” or “Pulling changes.”

## 0.8.28.5 — 2026-08-28

### Changed

- Made untraversed child directories diagnostic-only. A shallow push no longer
  creates a visible `directory/ ▸`; `-r` is required to synchronize it.
- Kept creation of the explicitly selected directory when it is required as a
  parent for selected files.

## 0.8.28.4 — 2026-08-28

### Added

- Added `hlsync --legend` as an offline, automatically colored reference for
  diff markers, directory notation, and untraversed-directory notation.

## 0.8.28.3 — 2026-08-28

### Changed

- Added `!` for excluded paths that exist remotely while retaining `x` for
  excluded paths that exist only locally; remote-present exclusions remain
  burnt orange.

## 0.8.28.2 — 2026-08-28

### Changed

- Changed excluded paths that exist remotely from dark cyan to burnt orange so
  they remain distinct from dark-blue untraversed directories.

## 0.8.28.1 — 2026-08-28

### Changed

- Removed the public `--color` option. HLSync now enables color only for terminal
  output and honors the conventional `NO_COLOR` environment variable.
- Kept `x` as the exclusion marker while rendering excluded paths that exist
  remotely in dark cyan instead of ordinary exclusion gray.

## 0.8.27.3 — 2026-08-27

### Changed

- Moved a diff's selected scope anchor to column zero and aligned every child
  beneath it, including neutral directories without visible status markers.

## 0.8.27.2 — 2026-08-27

### Changed

- Added `-i`, `--inc`, and `--included-only` to `hlsync list` to hide excluded
  entries consistently with `hlsync diff`.

## 0.8.27.1 — 2026-08-27

### Changed

- Renamed the installed CLI command from `hls` to `hlsync` across the console
  entry point, help and error output, resume commands, release validation,
  documentation, and website examples.
- Removed the old `hls` console entry instead of retaining a compatibility
  alias. The `hls` Python package, `~/.hls/configs.json` configuration path, and
  `hook-line-sync` PyPI distribution name remain unchanged.

## 0.8.26.17 — 2026-08-26

### Changed

- Compacted nested diff scopes into one full project-relative anchor such as
  `templates/partials/`, rather than printing every ancestor as a separate row.
- Indented entries relative to that anchor at any folder depth while continuing
  to start traversal directly at the selected directory.

## 0.8.26.16 — 2026-08-26

### Changed

- Preserved the complete project-relative ancestor chain when rendering a
  nested diff scope, so `hls diff templates/partials` displays `templates/` as
  the parent of `partials/` and indents its files beneath both.
- Kept reconstructed ancestors presentation-only; traversal still begins
  directly at the selected directory without listing its parents.

## 0.8.26.15 — 2026-08-26

### Changed

- Replaced the separate `d` directory type column with a conventional trailing
  `/` in list and diff output.
- Retained bright/dark blue directory coloring and the trailing `▸` traversal
  indicator as supporting visual cues.

## 0.8.26.14 — 2026-08-26

### Changed

- Made pull require an explicit file, directory, or pattern operand. Use
  `hls pull .` for the current directory and add `-r` for its complete subtree.
- Kept explicit pull directories shallow by default.

## 0.8.26.13 — 2026-08-26

### Changed

- Made bare `hls push` recursively synchronize the complete current subtree,
  equivalent to `hls push -r` and previewed by `hls diff -r`.
- Kept explicit directory operands shallow by default, so `hls push app`
  includes only `app` and its immediate contents unless `-r` is supplied.
- Left diff and pull default scope unchanged.

## 0.8.26.12 — 2026-08-26

### Changed

- Removed the redundant diff direction heading and per-directory comparison
  messages; command options establish direction and tree anchors establish
  directory scope.

## 0.8.26.11 — 2026-08-26

### Changed

- Moved the untraversed-directory `▸` indicator after the directory name so
  sibling directory and file names align at the same tree depth.

## 0.8.26.10 — 2026-08-26

### Changed

- Rendered diff paths as an indented tree relative to each selected scope,
  replacing repeated directory prefixes with basenames under a visible anchor.
- Retained full displayed paths for disjoint multi-root selections so identical
  basenames remain distinguishable.
- Kept full project-relative paths in selectors, comparison state, resume
  cursors, diagnostics, and transfer plans; only terminal presentation changed.

## 0.8.26.9 — 2026-08-26

### Changed

- Restored an explicitly selected directory as a blank-status `d directory`
  row, keeping the scope visible without implying content equality.
- Removed trailing ellipses from progressive `Comparing directory` messages.

## 0.8.26.8 — 2026-08-26

### Changed

- Removed the `=` status marker from directories that exist on both sides,
  because directory-entry equality does not establish content equality.
  One-sided and excluded directories retain their meaningful status markers.

## 0.8.26.7 — 2026-08-26

### Changed

- Removed the redundant `= d directory` row for an explicitly selected
  directory. The progress line identifies the scope, while one-sided,
  excluded, or actionable container states remain visible.

## 0.8.26.6 — 2026-08-26

### Changed

- Renamed the diff exclusion-display override to the positive
  `-i`/`--inc`/`--included-only` aliases.

## 0.8.26.5 — 2026-08-26

### Changed

- Replaced terminal-theme-dependent basic colors with explicit 256-color values
  for additions, retained local/remote paths, and included/excluded directories.
  This gives `+` vivid green, `r` dark teal-cyan, `l` bright cyan, and excluded
  directories a visibly darker blue than included directories.

## 0.8.26.4 — 2026-08-26

### Changed

- Made diff show unchanged and excluded entries by default and replaced
  `--all` with `--hide-excluded` for suppressing exclusion diagnostics.
- Kept excluded directories as visible traversal boundaries without walking
  their excluded subtrees, preserving recursive diff performance.
- Rendered unchanged `=` markers in the terminal's normal foreground color so
  gray remains exclusive to `x` exclusions.

## 0.8.26.3 — 2026-08-26

### Changed

- Made diff traversal local-led and start literal directory scopes directly at
  their selected local and remote paths. `hls diff var` now compares `var`
  without first listing the project root.
- Limited remote-only subtree traversal to explicitly requested remote pruning;
  ordinary diff traversal now follows the authoritative local tree.
- Separated directory traversal state from synchronization status. An
  untraversed directory now retains its `+`, `r`, or `=` status and adds a
  dark-blue italic `d ▸` indicator.

## 0.8.26.2 — 2026-08-26

### Changed

- Made push continue independent paths after path-scoped FTPS permission
  failures instead of stopping at the first rejected file or directory.
- Made a failed directory skip its subtree, report failed and dependency-skipped
  paths, return a nonzero command status, and suppress remote pruning after an
  incomplete upload phase.
- Kept session failures and uncertain replacement rollback failures fatal rather
  than continuing on an untrustworthy connection or remote state.

## 0.8.26.1 — 2026-08-26

### Changed

- Replaced the ambiguous retained-path `·` marker with side-specific `r` and
  `l` markers, using dark cyan for remote-only and bright cyan for local-only.
- Replaced the gray italic collapsed-directory ellipsis with a dark-blue italic
  `▸ d` state and moved unchanged `=` entries to dim default coloring, reserving
  gray status styling for `x` exclusions.

## 0.8.25.2 — 2026-08-25

### Changed

- Made shallow diffs display existing directories whose contents were not
  compared using a gray italic `… d` collapsed-directory state.
- Kept collapsed directories visible without `--all`, avoiding a false
  impression that their contents were checked and unchanged.

## 0.8.25.1 — 2026-08-25

### Changed

- Grouped synchronization-rule inspection by folder and sorted expressions by
  name while retaining stable precedence IDs.
- Made include and exclude updates remove an exact existing rule without adding
  a replacement when the remaining policy already produces the requested state.
- Sorted list and progressive diff entries like a file browser: directories
  first by name, followed by files by name at each level.

## 0.8.24.3 — 2026-08-24

### Changed

- Made no-argument diff, push, and pull inspect only the current directory's
  immediate contents; `-r`/`--recursive` explicitly includes the current
  subtree.
- Kept explicit directory operands on the same shallow-by-default contract so
  preview and transfer scopes remain identical.

## 0.8.24.2 — 2026-08-24

### Changed

- Applied one explicit-directory scope across diff, push, and pull: immediate
  contents by default and all descendants with `-r`/`--recursive`.
- Preserved full-project recursive behavior for no-argument diff and transfers,
  keeping scoped previews identical to their corresponding transfer plans.

## 0.8.24.1 — 2026-08-24

### Changed

- Made explicit directory operands in `hls list` display their immediate
  contents, with `-r`/`--recursive` extending through their descendants.
- Standardized the excluded-path marker as gray `x` in both list and diff.

## 0.8.23.15 — 2026-08-23

### Changed

- Made `hls list` default to the current directory's immediate children,
  including dotfiles, and added `-r`/`--recursive` for subtree listings.
- Kept explicit list selectors compatible while making `.` follow the new
  one-level default unless recursion is requested.

## 0.8.23.14 — 2026-08-23

### Changed

- Changed the local-list exclusion marker from `!` to `x` and applied the same
  automatic directory and exclusion coloring used by diff, with explicit
  `--color auto|always|never` control.

## 0.8.23.13 — 2026-08-23

### Changed

- Updated the homepage mini-diff to distinguish a preserved remote-only path
  (`·`) from an explicitly pruned path (`-`).

## 0.8.23.12 — 2026-08-23

### Changed

- Added diff-style, current-directory-aware path selectors to the local
  `hls list` command.
- Made remote pruning exclusive to push and its default diff projection;
  pull now rejects `--prune-remote`.
- Distinguished one-sided paths that will be kept (`·`) from projected remote
  deletions (`-`) in diff output.

## 0.8.23.11 — 2026-08-23

### Added

- Added `hls profile [PROFILE]` for inferred or explicitly selected profile
  details.
- Added a central interactive chooser for ambiguous command prefixes, with
  noninteractive ambiguity remaining a safe error.

### Changed

- Reduced `hls profiles` to a minimal name list with `*` marking the profile
  containing the current directory.

## 0.8.23.10 — 2026-08-23

### Added

- Added progressive, directory-at-a-time diff output, an `--all` audit view,
  and stateless `--paged`/`--resume` review commands.
- Added `hls profiles` as the dedicated configured-profile listing.

### Changed

- Made `hls list` the local mapped-tree view with visible exclusion status.
- Removed the overlapping `tracked`, `lsl`, and `lsr` commands.
- Applied diff selectors and exclusions before descending into remote
  directories, while leaving push and pull planning unchanged.

## 0.8.23.9 — 2026-08-23

### Changed

- Simplified rule displays by removing the `path`/`pattern` column: exact paths
  now use a display-only `./` prefix, while wildcard expressions remain
  unchanged.

## 0.8.23.8 — 2026-08-23

### Changed

- Rule listings and removal confirmations now label each rule as an exact
  `path` or reusable `pattern`, derived from its stored semantics without
  changing configuration schema 7.

## 0.8.23.7 — 2026-08-23

### Changed

- Replaced ambiguous generated usage for `hls list`, `hls exclude`, and `hls
  include` with explicit valid command forms.

## 0.8.23.6 — 2026-08-23

### Changed

- Replaced the ambiguous generated `hls rules` usage with explicit list and
  remove forms, and documented the role of each positional argument.

## 0.8.23.5 — 2026-08-23

### Changed

- Tightened four project-website labels to use plainer descriptions of
  exclusion, pushing, FTPS verification, and the core workflow.

## 0.8.23.4 — 2026-08-23

### Changed

- Repositioned the project website around the gap between manual FTP uploads
  and full deployment infrastructure, replaced abstract copy with concrete HLS
  behavior, and removed placeholder Field Notes that were not standalone
  articles.

## 0.8.23.3 — 2026-08-23

### Added

- Added a responsive PHP 8.3 project website for Apache shared hosting, with a
  terminal-inspired product overview, workflow, design principles, field-note
  previews, open-source support positioning, and deployment configuration.
- Extended release identity validation to prevent the standalone website from
  displaying a package version that has drifted from the CLI.

## 0.8.23.2 — 2026-08-23

### Changed

- Include and exclude now expand quoted and unquoted wildcard operands into the
  same exact local paths; the new `--pattern` flag explicitly records reusable
  wildcard rules.

## 0.8.23.1 — 2026-08-23

### Changed

- Diff output now uses a `d` type column for directories, distinct directory
  coloring, and a darker directory color for excluded entries.
- Excluded directory entries are now included in diff diagnostics alongside
  their excluded contents.

## 0.8.22.25 — 2026-08-22

### Fixed

- `hls diff *` now includes matching directory entries while retaining
  non-recursive traversal for non-recursive selectors.

## 0.8.22.24 — 2026-08-22

### Changed

- Renamed the remote-aware `hls compare` command to `hls diff`; removed the
  former `compare` and `cmp` spellings.

## 0.8.22.23 — 2026-08-22

### Changed

- Renamed `hls files` to `hls tracked` to distinguish the local eligible-file
  inventory from the remote-aware `hls compare` change plan.

## 0.8.22.22 — 2026-08-22

### Removed

- Removed the unrequested `hls explain` rule-diagnostic command.

## 0.8.22.21 — 2026-08-22

### Changed

- The current-directory mapping prompt during `hls add` now defaults to yes;
  the existing-mapping replacement prompt continues to default to no.

## 0.8.22.20 — 2026-08-22

### Changed

- `hls add` now proposes the current directory as the project's local root and
  maps it immediately after confirmation; declining leaves the project
  available for a later explicit `hls map`.
- `hls map` now prompts before replacing an existing local root, defaults to
  keeping it, and retains the project's relative synchronization rules when a
  replacement is confirmed.

## 0.8.22.19 — 2026-08-22

### Changed

- Shortened the schema-mismatch diagnostic while retaining its cause and
  recovery action.

## 0.8.22.18 — 2026-08-22

### Changed

- Configuration schema mismatch errors now report the stored and required
  versions, explain that synchronization-rule storage changed, and identify
  configuration recreation as the required recovery.

## 0.8.22.17 — 2026-08-22

### Added

- Added stable rule IDs, a unified ordered `hls rules` view, targeted `hls rules
  remove <id>` repair, and `hls explain <path>` winner diagnostics.

### Changed

- Replaced the mixed raw Gitignore `exclusions` array with explicit structured
  `include` and `exclude` records in intentionally incompatible configuration
  schema version 7.
- Replaced Gitignore matching with project-rooted HLS patterns: `*` matches one
  level, `**` is recursive, and literal directories cover their complete
  subtree.
- Exact repeated patterns now replace their earlier rule automatically without
  requiring manual cleanup.
- Removed the `pathspec` runtime dependency.

## 0.8.22.16 — 2026-08-22

### Changed

- Literal directory inclusion operands now persist as recursive `/**` rules,
  including directories produced by unquoted shell expansion such as
  `vendor/*`.
- No-argument `include` and `exclude` now list their respective persisted rules.
  Added `hls files` as the unified effective listing of all local files included
  in synchronization.

## 0.8.22.15 — 2026-08-22

### Added

- Added a one-command release preparation script that validates release
  identity, lint, tests, package metadata, and a clean wheel installation before
  placing version-specific artifacts under `dist/` for manual Twine upload.

### Changed

- Defined the initial voluntary Business Support benefits without restricting
  the MIT license or promising a service-level response time.
- Prepared the `hook-line-sync` PyPI distribution name while retaining `hls` as
  both the installed command and import package.

## 0.8.22.14 — 2026-08-22

### Added

- Added the Python package, `hls` console entry point, Python 3.10+ metadata,
  development tooling, and atomic configuration storage in
  `~/.hls/configs.json` without credential values.
- Added project lifecycle commands for adding, removing, listing, inspecting,
  and verifying FTPS projects. Production credential variables default to
  `PROD_FTPS_USERNAME` and `PROD_FTPS_PASSWORD`.
- Added verified explicit FTPS with `AUTH TLS`, protected `PROT P` data
  connections, certificate validation, structured MLSD listings, and no
  plaintext fallback.
- Added one canonical local root per project, recursive relative-path mapping,
  global overlap rejection, and current-directory project inference.
- Added deterministic local and remote tree inventories through
  `hls list local`, `hls list remote`, `hls lsl`, and `hls lsr`.
- Added push-oriented `hls compare`, its pull projection, compact colored status
  markers, immediately flushed progress, and `--prune-remote` / `-p` planning.
- Added shared path selection for compare, push, and pull, including literal
  paths, shell-expanded argument unions, quoted `*` and `**` patterns,
  selector-first traversal pruning, exclusion enforcement, unmatched-selection
  errors, and prune containment.
- Added executable push and pull pipelines with fresh comparison plans,
  conflict preflight, local-source revalidation, staged and size-verified
  uploads, remote timestamp preservation, recoverable remote replacement,
  atomic local replacement, and delete-last remote pruning.
- Added persistent ordered Gitignore rules through `hls exclude` and
  `hls include`, including comma-separated groups, shell-expanded operands,
  descendant re-inclusion, and exact project-relative anchoring for literal
  paths.
- Added complementary effective local-file listings through no-argument
  `exclude` and `include`, with explicit `--list` equivalents.
- Added compare-only diagnostic snapshots that display excluded files with a
  neutral gray `·` marker while keeping excluded paths out of transfers and
  pruning.
- Added unique command-prefix resolution with ambiguity errors.
- Added MIT licensing and documented the voluntary Business Support offering.

### Changed

- Project mapping now establishes only the local-root correspondence;
  synchronization rules are managed independently through `exclude` and
  `include`.
- Removed the superseded directory-scoped `hls use` mechanism.
- Standardized path-pattern argument parsing across compare, push, pull,
  exclude, and include.
- Kept `ls` and `cmp` as functional compatibility spellings while omitting them
  from the primary help menu.
- Stored synchronization rules are interpreted verbatim with ordered Gitignore
  last-match-wins semantics.

### Verification

- Added focused configuration and CLI characterization plus full local-to-FTPS
  and FTPS-to-local integration coverage against a disposable TLS-enabled FTP
  server.

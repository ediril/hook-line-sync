# Work Queue

- [x] Collapse the post-push remote-only report to one pruning hint instead of
  repeating paths already available through `diff`.
- [x] Report an empty transfer plainly and point push users to `-p` when
  selected remote-only paths are deliberately retained.
- [x] Align streamed transfer paths in a stable fixed-width operation column.
- [x] Stream plain-language path updates as transfer operations begin and
  replace the internal comparison table with a compact success summary.
- [x] Rewrite the README as a concise but complete current-user guide and
  document why safe FTPS replacement requires staging files.
- [x] Recover HLSync-owned abandoned upload and backup artifacts automatically
  within push scope without requiring remote-prune authorization.
- [x] Accept server-specific successful MFMT responses while independently
  verifying the staged timestamp with MDTM before installing an upload.
- [x] Replace internal push/pull plan terminology in progress output with plain
  comparison and transfer phases.
- [x] Make shallow child directories diagnostic-only so push does not create an
  untraversed directory while synchronizing its parent's immediate files.
- [x] Add an offline top-level `hlsync --legend` reference for diff symbols and
  their terminal colors without duplicating it across command help.
- [x] Distinguish excluded local-only paths with `x` from excluded paths that
  exist remotely with a burnt-orange `!`.
- [x] Separate remote-present exclusions from untraversed directories by using
  burnt orange rather than a cyan adjacent to the directory blues.
- [x] Detect color capability automatically, honor `NO_COLOR`, remove the
  public color override, and distinguish remote-present exclusions visually.
- [x] Align diff hierarchy from a column-zero scope anchor and stop reserving
  an invisible status column for neutral directories.
- [x] Add `-i`, `--inc`, and `--included-only` to `hlsync list` so its
  exclusion diagnostics can be hidden consistently with `hlsync diff`.
- [x] Rename the installed CLI command from `hls` to `hlsync` without changing
  the Python package, configuration path, or PyPI distribution name.
- [x] Continue independent push paths after path-scoped FTPS permission
  failures, skip descendants of failed directories, return a failing status,
  and suppress pruning after an incomplete upload phase.
- [x] Make diff traversal local-led and start literal directory selections at
  their exact local and remote paths instead of walking from the project root;
  retain ancestor inspection only when a wildcard has no narrower fixed prefix.
- [x] Make shallow diff scope visible with an independent trailing dark-blue
  italic `▸` traversal indicator, use dark/bright cyan `r` and `l` for retained
  remote/local paths, use trailing `/` plus blue coloring for directories, and
  reserve gray status styling for exclusions.
- [x] Group synchronization-rule inspection by folder while preserving visible
  precedence IDs, remove provably unnecessary exact rules during include or
  exclude updates, and use file-browser ordering in list and diff output.
- [x] Treat explicit `hlsync list` directory operands as containers and standardize
  the gray excluded-path marker as `x` across list and diff.
- [x] Make `hlsync list` current-directory-scoped by default, including dotfiles,
  with explicit `-r`/`--recursive` subtree traversal.
- [x] Use `x` and diff-consistent terminal coloring for excluded paths in
  `hlsync list`.
- [x] Align the homepage mini-diff with the push-only pruning markers.
- [x] Simplify inspection commands and make remote comparison interruptible:
  - [x] Use `profiles` for configured entries and `list` for the complete local
    tree with exclusion status; remove `tracked`, `lsl`, and `lsr`.
  - [x] Stream diff results one deterministic directory at a time.
  - [x] Show unchanged and excluded paths by default, with
    `-i`/`--included-only` for an included-path-only view.
  - [x] Add stateless `--paged` and `--resume` directory cursors.
- [x] Split profile inspection into a minimal `profiles` list and detailed
  `profile [PROFILE]` view, and interactively resolve ambiguous command prefixes
  without guessing in noninteractive use.
- [x] Give `list` the shared path-selector model and make remote pruning an
  explicitly push-only action with unambiguous diff markers.
- [x] Implement current-directory scope contracts for `diff`, `push`, and
  `pull`: bare push uses the complete current subtree, pull requires an explicit
  path, and diff plus explicit directory operands remain shallow unless `-r`
  is supplied.
- [x] Complete packaging documentation, release checks, and PyPI publication
  preparation:
  - [x] Define the concrete support and service benefits of the voluntary
    Business subscription without implying that the MIT license requires
    payment.
- [ ] Characterize and scale structured rule matching without requiring user
  discipline:
  - [x] Replace raw Gitignore entries with explicit, stable-ID HLS rules and
    automatically retain only the latest rule for an identical normalized
    pattern.
  - Index literal rules separately from wildcard rules while preserving their
    shared ordered reconciliation.
  - Characterize matching cost with hundreds and thousands of mixed rules.
- [ ] Characterize and improve FTPS scalability without weakening transfer
  guarantees:
  - Instrument directory listings, control-command round trips, data
    connections, bytes transferred, and elapsed time before selecting
    optimizations.
  - Measure shallow wide trees, deeply nested trees, many-small-file transfers,
    selector-pruned operations, and diff diagnostics that expose exclusions.
  - Add a way to omit excluded-file diagnostics when their remote traversal cost
    is unwanted.
  - Evaluate bounded, configurable concurrency using independent FTPS sessions,
    accounting for shared-host connection limits, deterministic failure
    handling, and existing staging guarantees.
  - Design a validated incremental remote manifest only if measurements justify
    it, with explicit invalidation for remote drift, interrupted transfers, and
    configuration or rule changes.
  - Document when FTPS is the limiting protocol and a VM transport such as SFTP
    or rsync is the appropriate production path.

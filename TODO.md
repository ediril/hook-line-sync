# Work Queue

- [x] Simplify inspection commands and make remote comparison interruptible:
  - [x] Use `profiles` for configured entries and `list` for the complete local
    tree with exclusion status; remove `tracked`, `lsl`, and `lsr`.
  - [x] Stream diff results one deterministic directory at a time.
  - [x] Add `--all` for unchanged and excluded paths.
  - [x] Add stateless `--paged` and `--resume` directory cursors.
- [x] Split profile inspection into a minimal `profiles` list and detailed
  `profile [PROFILE]` view, and interactively resolve ambiguous command prefixes
  without guessing in noninteractive use.
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

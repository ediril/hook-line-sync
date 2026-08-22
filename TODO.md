# Work Queue

- [ ] Complete packaging documentation, release checks, and PyPI publication
  preparation.
- [ ] Make persistent rule maintenance scale without requiring user discipline:
  - Automatically perform only provably semantics-preserving cleanup whenever
    `hls include` or `hls exclude` mutates the ordered rule list; do not expose
    a separate tidy command.
  - Retain the last identical rule, canonicalize safe syntax variants, and
    preserve Gitignore results for both current and future paths.
  - Index anchored literal rules separately from wildcard rules while preserving
    their shared ordering and last-match-wins reconciliation.
  - Characterize matching cost with hundreds and thousands of mixed rules.
- [ ] Characterize and improve FTPS scalability without weakening transfer
  guarantees:
  - Instrument directory listings, control-command round trips, data
    connections, bytes transferred, and elapsed time before selecting
    optimizations.
  - Measure shallow wide trees, deeply nested trees, many-small-file transfers,
    selector-pruned operations, and compare diagnostics that expose exclusions.
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

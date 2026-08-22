# Work Queue

- [x] Establish the executable foundation and configuration slice:
  - Add `pyproject.toml`, the `hls` package, console entry point, supported
    Python metadata, lint/test configuration, and a minimal README.
  - Define and validate the project-configuration model, including host, port,
    remote root, TLS settings, and credential environment-variable names.
  - Implement atomic persistence in `~/.hls/configs.json` without storing
    credential values.
  - Implement `hls add`, `hls remove`, `hls help`, and `hls version`.
  - Implement an explicit-FTPS transport that verifies certificates, enables
    `PROT P`, and has no plaintext fallback.
  - Cover configuration behavior with unit tests and FTPS connectivity with an
    integration test against a disposable TLS-enabled FTP server.
- [x] Implement one canonical local root per project with `hls map`, recursive
  relative-path correspondence and global overlap rejection.
- [x] Move synchronization scope out of `hls map`; implement persistent ordered
  `hls exclude` / `hls include` rules with comma-separated patterns, safe
  descendant re-inclusion, current-project inference, and unique command-prefix
  resolution while retaining established exact aliases.
- [x] Expose excluded files as gray neutral entries in compare-only diagnostic
  snapshots while keeping them absent from all transfer and prune plans.
- [x] Accept shell-expanded multi-argument patterns consistently in exclude and
  include while retaining comma-separated pattern groups.
- [x] Extract the common variadic pattern-operand grammar and normalization used
  by compare, push, pull, exclude, and include.
- [x] Remove the superseded directory-scoped `hls use` mechanism; project
  selection is inferred from non-overlapping local roots.
- [x] Implement deterministic `hls list` / `hls ls` project inventory, including
  endpoints, local/remote roots, exclusions, and current-directory inference.
- [x] Implement deterministic, exclusion-aware local and remote tree snapshots
  and `hls list local` / `hls list remote` with mapped-directory inference.
- [x] Specify timestamp normalization and comparison states, then implement
  push-oriented `hls compare` / `hls cmp`, its `--pull` projection, and
  `--prune-remote` / `-p` planning with full local-to-FTPS integration coverage.
- [x] Implement the shared optional file-selection model and apply it to compare:
  current-directory-relative literal paths, multiple shell-expanded paths as a
  union, quoted `*` / `**` patterns, exclusion enforcement, whole-union
  unmatched errors, prune containment, and pre-comparison traversal pruning on
  both local and remote snapshots.
- [x] Specify overwrite, selection, symlink, partial-transfer, and delete
  behavior; implement `hls push` with a fresh transfer plan and the shared
  optional file selector. Remote-only paths are reported and skipped unless
  `--prune-remote` / `-p` explicitly authorizes deletion after successful
  non-delete operations. Preserve and verify remote modification timestamps so
  completed uploads compare identically.
- [x] Implement comparison-selected push and verify the full local-to-FTPS
  pipeline.
- [x] Implement `hls pull` with atomic local replacement, the agreed overwrite
  behavior, the shared optional file selector, and opt-in `--prune-remote` /
  `-p` without restoring remote-only paths.
- [x] Implement comparison-selected pull and verify the full FTPS-to-local
  pipeline.
- [ ] Complete packaging documentation, release checks, and PyPI publication
  preparation.

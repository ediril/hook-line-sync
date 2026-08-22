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
  relative-path correspondence, global overlap rejection, and comma-separated
  gitignore-style exclusions.
- [x] Remove the superseded directory-scoped `hls use` mechanism; project
  selection is inferred from non-overlapping local roots.
- [x] Implement deterministic `hls list` / `hls ls` project inventory, including
  endpoints, local/remote roots, exclusions, and current-directory inference.
- [x] Implement deterministic, exclusion-aware local and remote tree snapshots
  and `hls list local` / `hls list remote` with mapped-directory inference.
- [x] Specify timestamp normalization and comparison states, then implement
  push-oriented `hls compare` / `hls cmp`, its `--pull` projection, and
  `--prune-remote` / `-p` planning with full local-to-FTPS integration coverage.
- [x] Implement the shared optional file-selector model and apply it to compare:
  current-directory-relative literal paths, quoted `*` / `**` patterns,
  exclusion enforcement, unmatched-selector errors, and prune containment.
- [ ] Specify overwrite, rename, glob, filter, symlink, partial-transfer, and
  delete behavior; implement explicit file and directory `hls push` with a
  fresh transfer plan and the shared optional file selector. Remote-only paths
  are reported and skipped unless
  `--prune-remote` / `-p` explicitly authorizes deletion after successful
  non-delete operations. Preserve and verify remote modification timestamps so
  completed uploads compare identically.
- [ ] Implement diff-selected push and verify the full local-to-FTPS pipeline.
- [ ] Implement explicit file and directory `hls pull`, including safe local
  writes, the agreed overwrite behavior, the shared optional file selector, and
  the same opt-in `--prune-remote` / `-p` behavior without restoring remote-only
  paths.
- [ ] Implement diff-selected pull and verify the full FTPS-to-local pipeline.
- [ ] Complete packaging documentation, release checks, and PyPI publication
  preparation.

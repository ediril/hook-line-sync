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
- [x] Implement the mapping model and `hls map`, including canonical absolute
  local paths, project-root-relative remote POSIX paths, persistence, and
  local/remote overlap rejection.
- [x] Implement directory-scoped `hls use` contexts with explicit project
  override, nearest-ancestor inheritance, inspection, clearing, and cleanup on
  project removal.
- [ ] Implement deterministic local and remote tree snapshots, then specify and
  implement `hls list local` and `hls list remote`.
- [ ] Specify timestamp normalization and comparison states, then implement
  `hls list diff` with full local-to-FTPS integration coverage.
- [ ] Specify overwrite, rename, glob, filter, symlink, and partial-transfer
  behavior; implement explicit file and directory upload.
- [ ] Implement diff-selected upload and verify the full local-to-FTPS upload
  pipeline.
- [ ] Implement explicit file and directory download, including safe local
  writes and the agreed overwrite behavior.
- [ ] Implement diff-selected download and verify the full FTPS-to-local
  download pipeline.
- [ ] Complete packaging documentation, release checks, and PyPI publication
  preparation.

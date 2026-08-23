# Changelog

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

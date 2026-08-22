# One local root per project

Date: 2026-08-21

## Decision

Each project has at most one canonical absolute local root. `hls map <project>`
sets it to the current directory. Every descendant maps to the same relative
path beneath the project's remote root. Local roots may not equal, contain, or
be contained by another project's local root.

The `hls use` command and directory-context storage are removed. Commands can
infer a project by locating the unique mapped local root containing their
canonical current path.

`hls map` accepts one optional `--exclude` value containing comma-separated,
gitignore-style wildcard patterns. Patterns are evaluated against POSIX paths
relative to the local root and apply to future listing, diff, push, and pull
operations. Excluded paths remain outside synchronization scope and are not
deleted remotely.

## Rationale

A project already owns its remote root, so parallel local-to-remote mapping
collections duplicate information and complicate selection. A single recursive
root correspondence makes subdirectory resolution mechanical and removes
ambient project-selection state. Global overlap rejection guarantees that
current-directory inference has exactly one answer.

## Consequences

- Configuration schema version 6 replaces mapping arrays with `local_root` and
  `exclusions` fields.
- Mapping an already-mapped project fails rather than replacing its root.
- Overlap is detected when `hls map` learns the local root, not when `hls add`
  creates an unmapped project.
- Exclusion patterns cannot contain commas, empty entries, `..`, or re-inclusion
  syntax beginning with `!`.
- The obsolete `~/.hls/contexts.json` file is ignored. The application does not
  delete it automatically.

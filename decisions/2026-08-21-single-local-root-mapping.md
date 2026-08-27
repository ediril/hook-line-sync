# One local root per project

Date: 2026-08-21

## Decision

Each project has at most one canonical absolute local root. `hlsync map <project>`
sets it to the current directory. Every descendant maps to the same relative
path beneath the project's remote root. Local roots may not equal, contain, or
be contained by another project's local root.

The `hlsync use` command and directory-context storage are removed. Commands can
infer a project by locating the unique mapped local root containing their
canonical current path.

`hlsync map` only establishes the root correspondence. Persistent synchronization
scope is managed independently by the ordered rules described in the
2026-08-22 command-prefix and synchronization-rules decision.

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
- Overlap is detected when `hlsync map` learns the local root, not when `hlsync add`
  creates an unmapped project.
- The obsolete `~/.hls/contexts.json` file is ignored. The application does not
  delete it automatically.

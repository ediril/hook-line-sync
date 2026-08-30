# Runtime identity

Date: 2026-08-29

## Decision

The installed console command and Python import package are both named
`hlsync`. Source code lives under `src/hlsync`, and runtime configuration lives
at `~/.hlsync/configs.json`. HLSync-owned local and remote staging artifacts use
the `.hlsync-` namespace.

The PyPI distribution remains `hook-line-sync`, matching the repository and
published package identity. The configuration schema uses `profiles` and has
version 8. Earlier `hls` imports, `~/.hls` configuration, `projects` schema
entries, and `.hls-` staging names are not recognized or migrated.

## Rationale

One runtime name removes the distinction between what users type, import, and
inspect on disk. A clean schema break is preferable while the tool is
pre-alpha because it avoids carrying aliases and migration paths for names that
no longer represent the domain.

## Intentionally excluded

- An installed `hls` command or import compatibility package.
- Reading or migrating `~/.hls/configs.json`.
- Accepting a `projects` configuration key.
- Recovering artifacts that use the old `.hls-` namespace.
- Renaming the `hook-line-sync` PyPI distribution or repository.

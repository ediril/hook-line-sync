# Deterministic project tree snapshots

Date: 2026-08-21

## Decision

`hls list local` and `hls list remote` snapshot the complete mapped project,
even when the current directory is a descendant of its local root. The current
directory selects the project but does not narrow the listing. An explicit
project name may be supplied as an override.

Snapshots contain relative POSIX paths and entry kinds, ordered lexically by
path. The same persisted gitignore-style exclusions are applied locally and
remotely. Excluded directories are pruned rather than traversed.

Local traversal uses filesystem entry metadata without following symlinks.
Symlinks appear in the snapshot as symlinks. Remote traversal requires MLSD and
recognizes files, directories, and Unix-style symbolic links; HLS does not fall
back to parsing server-specific `LIST` text.

## Rationale

Full-root snapshots give the future diff command two directly comparable views
regardless of where inside a project it is invoked. A shared representation
keeps selection and comparison independent of FTPS. MLSD supplies structured
entry facts, while `LIST` output has no portable grammar. Refusing to traverse
links prevents a snapshot from escaping the mapped tree or recursing through a
cycle.

## Consequences

- `hls list local [project]` requires a mapped project but no network access.
- `hls list remote [project]` connects securely and recursively lists the
  configured remote root over protected FTPS data connections.
- Servers without MLSD support fail explicitly; no unreliable fallback exists.
- File sizes and normalized modification timestamps are intentionally deferred
  to the next comparison-state decision.

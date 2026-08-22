# File timestamp comparison

Date: 2026-08-21

## Decision

Tree snapshots carry file size, UTC modification time in integer nanoseconds,
and the source timestamp's declared precision. Local snapshots use filesystem
nanosecond metadata. Remote snapshots require the MLSD `size` and `modify`
facts; incomplete or malformed file facts fail the snapshot.

Two files are identical when their sizes match and their timestamps match after
both are truncated to the coarser declared precision. Directories are identical
by path and kind. Type mismatches and symlinks are conflicts; HLS does not infer
symlink equivalence without portable remote target metadata.

## Rationale

MLSD timestamps are UTC and commonly have one-second precision, while local
filesystems expose finer timestamps. Comparing at the coarser reported
precision avoids treating unrepresentable subsecond differences as content
changes. File size prevents equal timestamps alone from hiding a clear change.

## Consequences

- Remote servers must provide structured MLSD type, size, and modify facts.
- Identical entries are retained in the comparison model but omitted from CLI
  output so the projection emphasizes actions and exceptions.
- Push must preserve and verify the local modification timestamp remotely. This
  is a structural requirement: without it, a successful upload may immediately
  compare as changed again.
- Hash comparison is not added because standard FTP does not provide a portable
  remote content-hash operation.

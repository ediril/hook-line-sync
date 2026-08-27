# File timestamp comparison

Date: 2026-08-21

## Decision

File snapshots carry size, UTC modification time in integer nanoseconds, and
the source timestamp's declared precision. Remote file snapshots require valid
MLSD `size` and `modify` facts.

Files compare as unchanged when their sizes match and their timestamps match
after both are truncated to the coarser declared precision. Directories compare
by path and kind only. A type mismatch or symlink is a conflict because no
portable remote metadata establishes equivalence.

## Rationale

Local filesystems commonly report finer time precision than FTP servers.
Comparing at the coarser available precision prevents false changes, while size
prevents equal timestamps from hiding an obvious content change.

## Intentionally excluded

- Treating timestamps alone as file identity.
- Comparing unrepresentable subsecond precision.
- A content-hash requirement, because standard FTP provides no portable remote
  hash operation.
- Parsing server-specific `LIST` output when structured MLSD facts are absent.

# File timestamp comparison

Date: 2026-08-21

## Decision

File snapshots carry size, UTC modification time in integer nanoseconds, and
the source timestamp's declared precision. Remote snapshots require valid size
and UTC timestamp facts normalized by the transport, whether read through MLSD
or through LIST with SIZE and MDTM. Listing-method selection belongs to the
[remote metadata decision](2026-09-13-remote-listings.md).

Files compare as unchanged when their sizes match and their timestamps match
after both are truncated to the coarser declared precision. A changed file is
replaced only when the source timestamp is strictly newer than the destination
at that same precision; a destination that is newer or ties is a conflict unless
the transfer is forced with `--force`. Directories compare
by path and kind only. A type mismatch or symlink is a conflict because no
portable remote metadata establishes equivalence.

## Rationale

Local filesystems commonly report finer time precision than FTP servers.
Comparing at the coarser available precision prevents false changes, while size
prevents equal timestamps from hiding an obvious content change.

Because transfers copy the source timestamp to the destination, an edit made
on either side after a sync makes that side newer, so a newer destination
marks changes a transfer would otherwise silently discard. The check is
stateless: it trusts the two clocks and cannot see that both sides changed since
the last sync when the source edit is the later one. A recorded per-profile sync
baseline (three-way comparison) would close that gap and was considered; the
stateless rule was chosen for simplicity.

## Intentionally excluded

- Treating timestamps alone as file identity.
- Comparing unrepresentable subsecond precision.
- A content-hash requirement, because standard FTP provides no portable remote
  hash operation.
- Using human-readable LIST dates or sizes as comparison metadata.

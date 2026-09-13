# Upload timestamps

Date: 2026-09-13

## Decision

Use MFMT for timestamp writes. For a server identifying itself as vsFTPd without
advertised MFMT, use its writable MDTM extension. Select this once per connection.
After either write, independently read MDTM and verify the source's whole-second
UTC timestamp before installing the staging file. Errors identify the failed
step and command; a rejected timestamp write never permits installation.

## Rationale

vsFTPd supports timestamp writes through MDTM rather than MFMT. A shared
verification step preserves the same transfer guarantee across both methods.

## Intentionally excluded

- Assuming every server advertising MDTM supports writing timestamps.
- Ignoring write failures or accepting successful replies without read-back.
- Retrying permission failures using alternative commands.

This extends the MFMT-only requirements in the remote-listing and transfer
decisions; staging, replacement, and cleanup retain their existing semantics.

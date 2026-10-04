# Remote metadata capabilities

Date: 2026-09-13

## Decision

Select the listing method from FEAT at connection time. Prefer MLSD when
advertised; otherwise use Unix-style LIST with SIZE and MDTM. Both methods
produce the same normalized facts for the tree model and exclusion processing.
LIST supplies names and entry types only; its human-readable dates and sizes
are not synchronization metadata. Request dotfiles with LIST -a in the selected
directory, then restore the connection's working directory. Failure to restore
that directory invalidates the session.

For upload timestamp writes, use MFMT. A server identifying itself as vsFTPd
without advertised MFMT uses its writable MDTM extension. Select the command
once per connection. After either write, independently read MDTM and verify the
source's whole-second UTC timestamp before installing the staging file.
A rejected write or failed read-back prevents installation.

## Rationale

FTPS servers such as vsFTPd support protected transfers without MLSD or MFMT.
SIZE and MDTM preserve exact size and UTC timestamp comparisons at the cost of
two requests per file. Normalizing both listing methods and verifying either
timestamp-write command preserve the same comparison and transfer guarantees.
Server compatibility stays inside the transport rather than becoming model or
transfer policy.

## Intentionally excluded

- Guessing metadata from LIST dates or accepting unrecognized listing formats.
- Following symlinks or traversing excluded directory boundaries.
- Retrying permission or connection failures using a different method.
- Assuming every server advertising MDTM supports timestamp writes.
- Accepting timestamp writes without independent read-back verification.

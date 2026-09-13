# Remote directory listings

Date: 2026-09-13

## Decision

Select the listing method from FEAT at connection time. Prefer MLSD when
advertised; otherwise use Unix-style LIST with SIZE and MDTM. Both methods
produce the same facts for the existing tree model and exclusion processing.
LIST supplies names and entry types only; its human-readable dates and sizes
are not synchronization metadata. Request dotfiles with LIST -a in the selected
directory, then restore the connection's working directory. Failure to restore
that directory invalidates the session.

## Rationale

FTPS servers such as vsFTPd support protected transfers without MLSD.
SIZE and MDTM preserve exact size and UTC timestamp comparisons at the cost of
two requests per file. Shared normalization keeps server compatibility out of
comparison and transfer policy.

## Intentionally excluded

- Guessing timestamps from LIST dates or accepting unrecognized listing formats.
- Following symlinks or traversing excluded directory boundaries.
- Retrying permission or connection failures using another listing method.
- Changing timestamp application during upload: MFMT and MDTM remain required.

This supersedes the MLSD-only restriction in the 2026-08-21 timestamp decision.

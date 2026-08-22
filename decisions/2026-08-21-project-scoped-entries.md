# Entries are projects with remote roots

Date: 2026-08-21

## Decision

Each named Hook Line Sync entry represents a project, not a unique server. A
project owns its FTPS endpoint, credential environment-variable names, required
absolute remote root, and local-to-remote mappings. Multiple projects may point
to the same FTPS host.

Mapping destinations were initially absolute and constrained to the owning
project's remote root. The later directory-context and relative-mapping decision
supersedes that representation. A project is removed locally with
`hls remove <project-name>`; removal deletes its configuration and mappings but
never connects to the server or deletes remote content.

## Rationale

The project is the unit a user intends to operate on. Treating an entry as a
server conflates connection reuse with destination identity and makes it harder
to distinguish separate deployments hosted by the same FTPS service. The
remote root creates an enforceable boundary around every project's mappings and
future transfers.

## Consequences

- Configuration schema version 4 uses a top-level `projects` object rather than
  `servers`.
- `hls add` requires both `--host` and `--remote-root`.
- Project names continue to derive credential environment-variable names unless
  explicit names are supplied.
- Earlier pre-alpha configuration files are rejected rather than migrated or
  interpreted through a compatibility path.

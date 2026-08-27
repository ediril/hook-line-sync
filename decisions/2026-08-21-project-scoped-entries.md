# Entries are projects with remote roots

Date: 2026-08-21

## Decision

Each named Hook Line Sync entry represents a project, not a unique server. A
project owns its FTPS endpoint, credential environment-variable names, required
absolute remote root, and local root mapping. Multiple projects may point
to the same FTPS host.

Mapping representation is governed by the later single-local-root decision. A
project is removed locally with
`hlsync remove <project-name>`; removal deletes its configuration and mappings but
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
- `hlsync add` requires both `--host` and `--remote-root`.
- The connection protocol is selected with `--protocol`; it defaults to `ftps`,
  the only currently supported value.
- Projects default to `PROD_FTPS_USERNAME` and `PROD_FTPS_PASSWORD`; either
  environment-variable name may be overridden explicitly.
- Earlier pre-alpha configuration files are rejected rather than migrated or
  interpreted through a compatibility path.

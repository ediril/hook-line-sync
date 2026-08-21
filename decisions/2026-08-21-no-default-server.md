# No default server profile

Date: 2026-08-21

## Decision

Hook Line Sync does not persist or use a default server profile. Commands that
operate on a profile directly, such as connection verification and mapping
creation, require its name explicitly. File operations will select their server
through an applicable persisted mapping; ambiguous selection must fail rather
than consulting ambient global state.

## Rationale

A mutable default can redirect a command without anything in that command
showing the effective destination. For a transfer tool, that convenience is not
worth the risk of uploading or downloading against the wrong server.

## Consequences

- The `hls set` command and top-level `default` configuration field do not
  exist.
- The configuration schema is version 2. Version-1 files from pre-alpha
  development are rejected rather than silently reinterpreted.
- A local path that matches mappings for more than one server will require an
  explicit disambiguation mechanism when transfer commands are implemented.

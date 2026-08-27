# No default project

Date: 2026-08-21

## Decision

Hook Line Sync does not persist or use a default project. Mapping creation and
project mutation require a name explicitly. Connection verification accepts an
explicit project, or infers one from the unique mapped local root containing the
current directory. File operations select their project through the same
persisted mapping; ambiguous selection must fail rather than consulting ambient
global state.

## Rationale

A mutable default can redirect a command without anything in that command
showing the effective destination. For a transfer tool, that convenience is not
worth the risk of uploading or downloading against the wrong project or server
location.

## Consequences

- The `hlsync set` command and top-level `default` configuration field do not
  exist.
- Removing the default advanced the pre-alpha configuration schema rather than
  adding a compatibility path.
- A local path that matches mappings for more than one project will require an
  explicit disambiguation mechanism when transfer commands are implemented.

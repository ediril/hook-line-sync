# Directory contexts and relative mapping destinations

Date: 2026-08-21

Status: Superseded by `2026-08-21-single-local-root-mapping.md`.

## Decision

`hlsync use <project>` associates a project with the canonical current directory.
The association applies to descendants through nearest-ancestor lookup and is
stored separately in `~/.hls/contexts.json`. An explicitly supplied project
takes precedence; otherwise a command uses the directory context and fails when
none exists. Filesystem root cannot own a context, so this mechanism cannot
become a global default.

The mapping command is:

```text
hlsync map <local-directory> [<relative-remote-directory>] [--project <name>]
```

Local input may be relative or absolute, but mappings persist its canonical
absolute path. The remote directory is persisted relative to the project's
remote root. When omitted, it is the canonical local directory's basename; an
explicit `.` means the project root.

This supersedes the earlier decision in
`2026-08-21-project-scoped-entries.md` that mapping destinations remain
absolute.

## Rationale

Directory scoping provides convenience without allowing a choice made in one
workspace to redirect commands in unrelated directories. Relative remote
destinations make the project root authoritative and avoid repeating it in
every mapping command. Persisting canonical absolute local paths keeps matching
deterministic regardless of the spelling or working directory used at creation.

## Consequences

- `hlsync use` displays the inherited context, `hlsync use <project>` sets one, and
  `hlsync use --clear` removes the context set at the current directory.
- Removing a project also removes directory contexts that name it.
- Absolute remote mapping arguments and `..` traversal are rejected.
- Configuration schema version 5 stores relative mapping destinations. Context
  storage has its own versioned schema.

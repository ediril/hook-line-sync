# CLI command name

Date: 2026-08-27

## Decision

The installed console command is `hlsync`. The former `hls` entry point is
removed rather than retained as a compatibility alias. User-facing usage,
errors, generated resume commands, release checks, documentation, and website
examples use `hlsync`.

The PyPI distribution remains `hook-line-sync`, the internal Python package
remains `hls`, and configuration remains at `~/.hls/configs.json`. Existing
profiles and rules therefore require no migration.

## Rationale

`hlsync` communicates synchronization more clearly at the shell and avoids the
many unrelated meanings of `hls`. Renaming only the console boundary delivers
that clarity without creating needless import or configuration churn.

## Consequences

- Reinstalling the package creates `hlsync`, not `hls`.
- Scripts and shell history that invoke `hls` must be updated.
- Python imports continue to use `hls`.
- Existing configuration is read without conversion.

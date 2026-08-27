# CLI command name

Date: 2026-08-27

## Decision

The installed console command is `hlsync`. User-facing usage, errors, generated
commands, release checks, documentation, and website examples use that name.

The PyPI distribution remains `hook-line-sync`, the internal Python package
remains `hls`, and configuration remains at `~/.hls/configs.json`.

## Rationale

`hlsync` describes synchronization clearly at the shell and avoids the many
unrelated meanings of `hls`. Renaming only the console boundary avoids needless
package and configuration churn.

## Intentionally excluded

- An installed `hls` compatibility alias.
- Renaming the Python import package, distribution, or configuration path.

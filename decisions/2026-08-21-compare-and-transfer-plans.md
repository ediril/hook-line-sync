# Comparison and transfer planning

Date: 2026-08-21

## Decision

`hlsync diff` is a read-only projection of the actions a transfer would take
over the selected scope. It uses push perspective by default; `--pull` reverses
the direction for changed files without changing the rule that local path
existence is authoritative.

A remote-only path is retained and reported by default in either perspective.
Push comparison accepts `--prune-remote` / `-p` to project its deletion; pull
rejects pruning. A local-only path is eligible for push but is retained during
pull rather than being overwritten or removed.

Diff and transfer commands share selection and planning semantics. A real
transfer always takes fresh snapshots and builds a new plan immediately before
mutation; displayed output is never an executable cached plan. Excluded paths
are treated as absent from the authoritative local set: they are never uploaded
or pulled, remain `!` diagnostics when present remotely, and become remote
deletions only when push pruning is explicitly authorized.

## Rationale

One planning model keeps preview and execution aligned. Local-authoritative
existence prevents pull from resurrecting intentional local deletions, while an
explicit prune flag separates evidence of remote-only content from authority
to delete it. Treating exclusions as local absence gives the same pruning rule
to physically missing and deliberately omitted local paths.

## Intentionally excluded

- Separate push and pull dry-run modes.
- Executing a previously displayed or persisted plan.
- Automatically restoring a remote-only path during pull.
- Automatically deleting remote-only content without explicit push pruning.
- Uploading or pulling excluded paths.
- Deleting a remote copy of an excluded path without explicit push pruning.

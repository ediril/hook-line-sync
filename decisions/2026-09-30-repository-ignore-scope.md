# Repository-scoped Git ignore defaults

Date: 2026-09-30

## Decision

Git-ignored paths are excluded by default; explicit HLSync inclusion rules
override that baseline. A mapped folder can sit any number of levels below
its repository root. Find the nearest enclosing `.git` directory or file and
evaluate every applicable `.gitignore` from that root through the mapped tree.
A `.git` file supports worktrees and submodules without invoking Git or reading
their metadata. If no repository encloses the profile, start at the mapped root.

Evaluate patterns relative to the directory containing each ignore file.
Preserve anchored patterns, deeper negations, and ignored-parent boundaries.
Load and cache ignore files lazily for each command, without scanning siblings
or following symlinked ignore files. Keep all public paths profile-relative.

## Rationale

A deployment folder such as `site/public` must inherit the repository's ignore
policy even when its `.gitignore` lives several levels above the mapped folder.
A fixed ancestor count would make behavior depend on arbitrary folder depth.

This supersedes the profile-only ancestor limit in the September 14 decision.
Git's global excludes, index/tracked status, and `.git/info/exclude` remain
outside this `.gitignore` baseline. Local exclusions retain their existing
transfer semantics; they do not become remote protection rules.

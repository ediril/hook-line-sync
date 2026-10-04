# Git ignores as the local baseline

Date: 2026-09-14

## Decision

Read `.gitignore` files lazily using pathspec's GitIgnoreSpec matcher. A mapped
folder can lie at any depth below its repository root. Find the nearest enclosing
`.git` directory or file and evaluate applicable ignore files from that root
through the mapped tree. A `.git` file supports worktrees and submodules without
invoking Git or reading their metadata. With no enclosing repository, start at
the mapped root.

Evaluate patterns relative to each ignore file's directory. Preserve anchored
patterns, deeper negations, and ignored-parent boundaries. Cache parsed files
for one command without scanning siblings or following symlinked ignore files.
Keep public paths profile-relative and never copy ignore patterns into stored
configuration.

Explicit HLSync rules override Git ignores: global rules first, profile rules
last. Rule cleanup must preserve an inclusion needed to override the baseline.
Use the same effective RuleSet for local and remote classification across list,
diff, push, and pull. Git ignores affect local eligibility, not remote protection.

## Rationale

Project ignores reduce manual configuration while explicit deployment inclusions
allow Git-ignored build artifacts to be deployed. A maintained matching library
avoids a second custom wildcard dialect. Repository-based scope ensures a
mapping such as `site/public` inherits its project's policy regardless of depth.
Lazy command-local caching avoids a separate recursive ignore scan.

## Intentionally excluded

- A Git executable dependency, index/tracked-file handling, global Git excludes,
  or `.git/info/exclude`.
- Automatic remote protection or a configuration migration.
- A fixed ancestor count, sibling scans, or symlinked ignore files.

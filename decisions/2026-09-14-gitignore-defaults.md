# Git ignores as the default local baseline

## Rule

Read profile-root and nested `.gitignore` files lazily, using pathspec's
GitIgnoreSpec matcher. Respect directory scope and ignored parent boundaries.
Do not follow symlinked ignore files or consult ancestors outside the profile.
Cache parsed files for one command; never copy patterns into configuration.

Explicit HLSync rules override Git ignores: global rules first, profile rules
last. Rule cleanup must retain an inclusion needed to override a Git ignore.
Use the same effective RuleSet for local and remote classification across
list, diff, push, and pull. Git ignores affect local eligibility, not remote
protection. Existing pruning semantics remain unchanged.

## Why

Existing project ignores reduce manual configuration. Explicit deployment
inclusions cover Git-ignored build artifacts without editing `.gitignore`.
A maintained matching library avoids a second custom wildcard dialect.

## Excluded

No Git executable, index/tracked-file handling, global Git excludes, automatic
remote protection, configuration migration, or eager recursive ignore scan.

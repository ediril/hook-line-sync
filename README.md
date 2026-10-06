# Hook Line Sync

Hook Line Sync (`hlsync`) is a command-line workflow for deploying local
projects to shared hosting over explicit FTP over TLS (FTPS): map once, preview
the diff, then push the intended files.

HLSync is pre-alpha software. Commands and configuration may change before a
stable release.

## Who is it for?

HLSync is for people who still deploy websites or small projects to shared hosting over FTP.

If your current process is basically “figure out which files changed and upload them,” HLSync gives you a safer, more repeatable version of that workflow without requiring a full deployment system.

It works best when your local project is the source of truth and the remote server is simply where the project gets deployed.

## Installation

HLSync requires Python 3.10 or newer. Install it from PyPI as an isolated
command-line tool with uv:

```console
uv tool install hook-line-sync
```

Upgrade later with:

```console
uv tool upgrade hook-line-sync
```

The FTPS server must support explicit TLS with protected data connections
(`AUTH TLS` and `PROT P`). HLSync prefers MLSD listings; servers without MLSD
use Unix-style LIST listings with SIZE and MDTM for exact file metadata.
LIST mode includes dotfiles and requires two extra requests per file. Push additionally
requires MFMT (or writable MDTM on vsFTPd) and MDTM read-back to apply and verify
uploaded-file timestamps.

## Quick start

HLSync reads credentials from environment variables. The defaults are:

```text
PROD_FTPS_USERNAME
PROD_FTPS_PASSWORD
```

From the local project root:

```console
hlsync create prod --host ftp.example.com --remote-root /public_html/site
hlsync connect
hlsync rules -e .git node_modules
hlsync diff
hlsync push
```

`create` proposes the current directory as the local root; pressing Enter accepts
it. Declining prompts for another local folder. Use `--local-root PATH` to
provide one directly. Both `diff` and `push` recurse by default. Use `-s` /
`--shallow` to process only the selected folder's immediate contents.

## Profiles and mapping

A profile identifies one deployment target: protocol, host, port, remote root,
credential environment-variable names, and one local root. Multiple
profiles may use the same server. Credential values are never stored in
`~/.hlsync/configs.json`.

FTPS is the default and currently the only protocol. Override credential
variable names when creating a profile if needed:

```console
hlsync create staging \
  --host ftp.example.com \
  --remote-root /public_html/staging \
  --local-root /path/to/project \
  --username-env STAGING_FTPS_USERNAME \
  --password-env STAGING_FTPS_PASSWORD
```

HLSync stores the canonical absolute local root and maps every descendant to
the same relative path under the remote root. Roots may not overlap across
profiles. Remapping requires confirmation and defaults to no.

Use `map` to change either side after creation. Omit `--local-root` to use the
current directory; changing only the remote root preserves the local root:

```console
hlsync map staging --local-root /new/local/path
hlsync map staging --remote-root /new/remote/root
```

The normal workflow is to run HLSync inside a mapped root or one of its
descendants. The current directory selects the containing profile and relative
local scope automatically:

```console
hlsync profiles          # all profiles; * marks the current one
hlsync profile           # current profile name
hlsync profile --details # current profile details
hlsync profile staging   # verify and print a named profile
hlsync profile staging --details
hlsync root staging      # print the mapped local root only
hlsync connect            # verify FTPS, then disconnect
hlsync remove staging    # remove local configuration only
```

Outside every mapped root, `hlsync profile` reports that no profile is active
and suggests `hlsync PROFILE COMMAND`. Commands that require a profile need
that explicit profile prefix. Named and inferred lookups both require
`--details` for the full view.

Because `root` writes only the canonical path, it can be composed with the
shell when you want to switch directories:

```console
cd "$(hlsync root staging)"
```

An unqualified profile-aware command fails outside every mapped root. When you
intentionally need to operate from elsewhere—or override the profile inferred
from the current directory—put the profile before the command. The override
lasts for that command only and uses the selected profile's local root as its
working directory:

```console
hlsync staging list
hlsync staging diff templates
hlsync staging push templates -r
```

No profile selection is persisted between commands.

## Synchronization rules

HLSync automatically honors `.gitignore` files as local exclusions. When the
mapped local root is inside a Git repository, this includes all ancestor
`.gitignore` files up to the nearest repository root, plus files inside the
mapped tree. Without an enclosing repository, ignore scope starts at the mapped
root. Git worktrees are supported; no Git installation is needed.
Explicit HLSync rules override this baseline; profile rules override global rules.
To deploy a Git-ignored path, use `hlsync rules -i vendor/` (or a specific file).
Ignore files above the repository root, Git's global excludes, and the Git index
are not consulted; matching tracked files are excluded too.

**Review `hlsync push --dry -p` before pruning:** with `-p`, locally excluded
files that are already deployed are deleted remotely. Without `-p`, their remote
copies are left alone; remote exclusion rules protect paths even when pruning.

Global rules live in `~/.hlsync/rules.json`, apply to every profile, and are
created with default exclusions for version-control metadata and common logs:

```text
**/.git/**
**/.svn/**
**/.hg/**
**/.DS_Store
**/Thumbs.db
**/desktop.ini
**/.gitignore
**/.gitmodules
**/error_log
```

Manage global exclusions and inclusions from any directory with `-g` /
`--global`. Global operands are reusable patterns rooted at every profile's
local root; append `/` to target a complete directory tree:

```console
hlsync rules -e -g --pattern '*.tmp'
hlsync rules -i -g --pattern 'public/*.tmp'
hlsync rules -g                    # inspect global rules
hlsync rules --remove g4           # g prefix selects global rules
```

Global rules apply first and profile rules apply afterward, so an ordinary
profile inclusion can override a global exclusion. `hlsync rules` merges both
layers into one folder-grouped view, placing matching profile rules after
global rules. Global rules have `g`-prefixed IDs such as `g4`; profile rule IDs
remain numeric. IDs identify only current rules and may be reused after a rule
is removed. HLSync never silently adds new defaults to an existing global
rules file.

Exclude current paths permanently:

```console
hlsync rules -e .git node_modules composer.json composer.lock
hlsync rules -e '*.md'
```

Normal wildcard operands are expanded against the current local tree and
recorded as exact paths. Quote them so the shell does not reject or alter them;
quoted and shell-expanded matches produce the same path rules.

Use `--pattern` when future matching paths should also be covered:

```console
hlsync rules -e --pattern '*.md'       # this directory only
hlsync rules -e --pattern '**/*.log'   # every directory below this point
hlsync rules -i --pattern 'vendor/**'  # re-include a subtree
```

Use `--anywhere` (or `--any`) to match a name at every depth, including future
files. It works with both `-e` and `-i`, and replaces `--pattern`:

```console
hlsync rules -e --anywhere filename.ext  # current directory and descendants
hlsync rules -e --any '*.log'            # quote wildcards to preserve the pattern
hlsync rules -e -g --anywhere cache/     # matching directory trees in every profile
```

`*` matches within one path segment; a complete `**` segment crosses directory
levels. Patterns are rooted where the command runs. HLSync rules are not
Gitignore syntax: `!`, `?`, bracket patterns, absolute paths, parent traversal,
and partial-segment `**` are rejected.

Local rules define the authoritative local set. Remote rules instead protect
server-side paths from synchronization:

```console
hlsync rules -e --remote subdomains
hlsync rules -i --remote subdomains
```

Remote operands are declarative and never require a connection when recorded.
`subdomains` and `subdomains/` store the same exact boundary. During diff or
push, an existing remote file is left untouched; an existing remote directory
and everything beneath it are left untouched without traversing the directory.
A matching remote inclusion removes or overrides that boundary and returns the
path to normal push policy. Remote directory boundaries cannot be pierced by a
more specific child inclusion. `hlsync rules` groups the two rule targets under
`Local` and `Remote`.

Local rules keep the original compact JSON form. A missing stored `target`
means local; only remote rules add `"target": "remote"`.

Rules have stable IDs and the highest matching ID wins. HLSync removes provably
redundant exact rules but preserves ambiguous wildcard overlaps.

```console
hlsync rules
hlsync rules --remove 3
```

Multiple operands and comma-separated groups are accepted. A literal filename
containing a comma cannot be addressed because commas delimit groups.

## Paths and traversal

Paths are relative to the current directory inside the mapped root. Multiple
paths and wildcard patterns form one deterministic selection. Absolute paths,
parent traversal, and paths escaping the mapped root are rejected.

| Command | No path | Explicit directory | Depth option |
| --- | --- | --- | --- |
| `list` / `list --remote` | Current directory, one level | Directory contents, one level | `-r` includes descendants |
| `diff` | Complete current subtree | Complete directory subtree | `-s` limits to immediate contents |
| `push` | Complete current subtree | Complete directory subtree | `-s` limits to immediate contents |
| `pull` | Error: path required | Directory contents, one level | `-r` includes descendants |

Diff and push accept `-s` / `--shallow`; `-r` / `--recursive` remains available
to explicitly select the default. The two flags cannot be combined.

`.` explicitly selects the current directory. An immediate child directory
outside the traversal depth appears with `▸` but is diagnostic-only: it is not
created, replaced, deleted, or entered. The selected directory itself may be
created when selected files require it as their parent. An explicitly selected
remote-only directory is the deletion target itself, so recursive push
enumerates that subtree and removes its contents deepest-first. With `-s`,
deeper folders and their deletion ancestors are retained.

## Local and remote listing

`list` reads only the local filesystem, includes dotfiles, and applies the
configured rules:

```console
hlsync list
hlsync list templates
hlsync list '*.md'
hlsync list -r
hlsync list -r -i
```

Use `--remote`—or the `lsr` shorthand—to inspect the equivalent FTPS
tree with the same operands and traversal controls:

```console
hlsync list --remote
hlsync list --remote templates -r
hlsync lsr
```

Remote listing connects read-only. Remote-excluded paths use `#` and their
directories are shown as boundaries without being entered.

Directories appear before files at each level, with each group sorted by name.
Directories end in `/`; local exclusions use `x`, remote exclusions use `#`.
Single-side listings do not report whether the other side has a copy. `-i`, `--inc`, and
`--included-only` hide excluded paths. `hlsync ls` remains an unadvertised
compatibility spelling.

## Diff

`diff` is read-only and shows what the corresponding push would do:

```console
hlsync diff
hlsync diff templates
hlsync diff -s
hlsync diff templates --shallow
hlsync diff index.html app.js styles.css
hlsync diff '**/*.css'
```

Local path existence decides what is uploaded or replaced. In the default
push view, remote-only paths are retained because push never deletes without
`-p`. Preview a pruning push with:

```console
hlsync diff --prune
hlsync diff -p
```

`--pull` changes the perspective for changed existing files and retains
remote-only paths. Diff normally shows actionable differences, retained
one-sided paths, conflicts, and local or remote exclusion boundaries. Use
`-i`/`--inc`/`--included-only` to hide exclusions. Use `-a`/`--all` to restore
unchanged and untraversed entries for the complete exploratory view.
Recursive diff keeps file-browser order in both views: directories and their
indented contents appear before files at the parent level.
Rows without status markers retain blank status columns so names stay aligned.
Status columns stay fixed at the left; tree indentation applies to path names.
The status has three slots: action (`+`, `~`, `-`, `?`, `=`), exclusion
(`x` local, `#` remote), and presence (`l`, `r`, or blank for both sides), so
`-x` marks an excluded path that `--prune` would delete.
The `▸` marker means contents were not inspected, including excluded folders.
Diff reads directories as it traverses the tree and groups their entries under
folder headings, without separate per-directory read announcements.

For pruning, a locally excluded file is treated as absent. If it exists
remotely, default diff marks it ` x` and retains it; `diff -p` marks its
deletion as `-x`. The presence column still reports the actual copies:
blank when both exist, `r` when only the remote copy exists. An excluded
directory is a traversal boundary and is retained with `x`. An explicit local
inclusion for a descendant permits traversal;
remote exclusions remain hard boundaries. `-i` never hides an actionable deletion.

Diff enters eligible child folders by default. `diff -s` or
`diff templates --shallow` reads only immediate contents. Unentered child
folders retain the `▸` marker and are retained, matching `push -s`; an
unentered remote-only folder appears as `   r folder/ ▸`. Without `-p`, diff
does not enter remote-only folders, since push would neither change nor
delete their contents.

Show the current status and directory notation without connecting:

```console
hlsync --legend
```

Diff prints each directory as it is compared. For a shell-driven review,
`--paged` prints one directory, exits, and provides the exact stateless
`--resume` command for the next deterministic directory.

Colors are automatic on terminals, disabled for pipes and redirection, and
suppressed when `NO_COLOR` is set. Text markers retain the core meaning without
color. The left column reports action or status: `x` means locally excluded
and `#` means remotely excluded. The right column reports presence: `l` means
local only, `r` means remote only, and a blank means both sides. For example,
`x   notes/ ▸` exists on both sides but is locally excluded, while
`# r millionminds/ ▸` exists only remotely and is remotely excluded. Exclusion
source never changes the presence column.

## Push and pull

Push local changes or replace explicitly selected existing local files from the
remote side:

```console
hlsync push
hlsync push templates
hlsync push templates -r
hlsync pull index.html
hlsync pull templates -r
```

Push uploads local-only files and replaces changed remote files. Pull replaces
changed existing local files but never restores a missing local path. Locally
excluded paths are never uploaded or pulled; remote-excluded paths are not
traversed or changed. Push never deletes unless `-p` / `--prune` is given;
then it deletes selected remote-only paths, including remote copies of locally
excluded files. Excluded directories on
either side are retained and never entered; an explicit local inclusion beneath
an excluded local directory is the only reason to enter that local boundary.
Push recurses into selected directories by default, including remote-only
deletion targets when pruning. `-s` /
`--shallow` processes immediate contents without entering child folders,
creating them, or deleting them. A selected remote-only directory containing
an unentered child folder is also retained.

Preview the exact push scope and operation order without changing either side:

```console
hlsync push --dry
hlsync push templates --dry
hlsync push templates -s --dry
```

Both `diff` and `push --dry` inherit push's recursive default. Dry push
honors `-s`, `-p`, remote exclusions, and explicit directory scope exactly as a
real push would. Interrupted-upload recovery is projected and reported but not
performed. After planning, dry push runs the live transfer executor and skips
only its mutation calls, preserving preflight, operation order, feedback, and
counts.

Dry and live push identify each local and remote directory as they scan it. A
parent is fully classified before HLSync enters eligible children, and excluded
directories are never entered. Dry-run plans use diff's compact colored `+`,
`~`, and `-` action markers under an explicit dry-push heading.

Live transfers print the colored `+`, `~`, or `-` action and path after each
operation succeeds. Failures and skips appear immediately; the final summary
contains counts without repeating errors. Dry runs use the same feedback to
show planned operations without performing them.
When no operation is needed, HLSync prints `Nothing to push` or `Nothing to
pull` without announcing an empty transfer phase. An empty push also reports
how many included files are up to date in the selected scope. Push summaries
report the outcome without a retained-path reminder.

After scanning, push shows the planned upload count and total size. Interactive
terminals show remote reads as completed/discovered directories (such as 2/12)
and the current path, without animation. The discovered total grows as eligible
subdirectories are found. During uploads, interactive
terminals display a progress bar with bytes sent and files installed. File
counts advance only after timestamp verification and installation; failures
remain visible immediately. Redirected output keeps ordinary per-file logs.
Dry runs show planned totals without simulating byte progress.

Delete selected remote-only paths explicitly with:

```console
hlsync push --prune
hlsync push -p 'generated/*.html'
```

Deletion is limited to the selected scope, runs only after every upload
succeeds, and is suppressed after any upload failure. Pull never deletes remote
paths.

### Safe file replacement

Remote ownership and permissions are controlled by the server. HLSync does not
apply local modes or issue remote chmod/chown commands. Staging files are created
beside their destinations and retain server-assigned permissions when installed.
For shared writable app-data trees (for example, `ftps-deploy` and `www-data`),
configure setgid directories and an appropriate umask or default ACL to create
`664` files and `2775` directories. Setgid alone does not grant group write;
replacement files receive the staging file's mode, not the old file's mode.

HLSync never uploads directly over a live destination. A direct FTP upload can
truncate or expose a partial live file when the connection fails. Instead,
HLSync:

1. Uploads to a uniquely named staging file beside the destination.
2. Verifies its size.
3. Applies the local whole-second UTC timestamp with MFMT (writable MDTM on
   vsFTPd) and independently
   reads it back with MDTM.
4. Moves the existing destination to a temporary backup.
5. Renames the verified staging file into place, then removes the backup.

This makes each file replacement recoverable, not the complete project
transactional—FTPS has no project-wide transaction. A later failure does not
roll back files already installed.

During a push, HLSync recovers its exact reserved artifacts as each selected
remote directory is read. It does not perform a separate recursive cleanup
scan. Abandoned upload files are deleted; obsolete backups are deleted when
their destination exists; a sole backup is restored when its destination is
missing. This cleanup is independent of remote-only deletion policy and does
not affect ordinary remote-only files. Concurrent pushes to one profile are not
supported.

A path-scoped permission failure skips that path or unwritable subtree while
independent paths continue. The command exits nonzero and suppresses all
pruning. Type or symlink conflicts, connection failures, and failed replacement
recovery on selected paths stop the operation when continued state cannot be
trusted.

## Command behavior

Commands accept the shortest unique prefix. Exact names win. An ambiguous
prefix prompts for a numbered choice on an interactive terminal and fails with
the candidate list in noninteractive use.

Use `hlsync help [command]`, `hlsync version`, and `hlsync --legend` for
built-in reference. `hlsync v`, `hlsync -v`, and `hlsync --version` also print
the installed version.

## License

HLSync is available under the [MIT License](LICENSE) for personal and commercial
use. A future voluntary Business subscription may fund development and provide
support or services; it is not required for commercial use.

## Development and maintenance

Install the development environment and run the test suite:

```console
python -m pip install -e '.[dev]'
pytest
```

To try local changes using your installed `hlsync` command, run this from the
repository root:

```console
uv tool install --force --reinstall .
```

This replaces the installed tool with a build of your current checkout. Rerun
it after making changes. Use `hlsync --legend` for a quick display check, or
run `hlsync diff` from a mapped project to preview its differences.

The PyPI distribution is `hook-line-sync`; the installed command and Python
package are both `hlsync`. See [`TODO.md`](TODO.md) for the
ordered work queue and [`CHANGELOG.md`](CHANGELOG.md) for completed changes.
[`decisions/`](decisions/) holds substantial architectural choices and their
rationale. CLI conventions and current usage are documented here; smaller
changes are explained in commit messages.

The self-contained PHP 8.3 project site is in [`website/`](website/README.md).

### Releasing to PyPI

Releases use `<major>.<work-day>.<increment>` without leading zeroes. Versions
come from Git history, not the build date or manually maintained counters:

- [`version.json`](version.json) selects the major number and its baseline
  commit. Version 1 starts at `b309f3e` ("done with mvp", August 22, 2026).
- The baseline day is `0`. Each subsequent date with commits advances the
  work-day number by one, regardless of how many idle days pass.
- The increment counts commits on that date, starting at `1`. On the baseline
  day, only the baseline commit and later commits count.
- Dates use each commit's recorded committer date and timezone. Only the
  first-parent history of the current checkout counts; a merge counts once.
  All commits count, including documentation and maintenance changes.

For example, two commits on the baseline day are `1.0.1` and `1.0.2`.
The next day with a commit produces `1.1.1`, even after a week without changes.
The September 30 commit `778ba7d` is `1.13.9` under this scheme.

Builds require history back to the baseline and reject backwards-moving commit
dates. Wheels and source archives preserve the computed version; installed
commands do not access Git. Reinstall editable checkouts after committing to
refresh their installed version. To start a new major, update `version.json`
with the new major and an existing baseline commit on the same first-parent
history. That baseline starts at `<major>.0.1`.

Use an existing PyPI account with two-factor authentication and an API token.
Twine uses credentials from `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD`,
and prompts if needed. Do not store the token in the repository.

1. Commit the changes to release. Use a checkout with history back to the
   baseline in `version.json`. Do not edit the generated `_version.py`.
2. Update [`CHANGELOG.md`](CHANGELOG.md) when useful. Release notes and dated
   headings are optional and do not block publishing.
3. Commit any release-note changes. From that clean checkout, with development
   dependencies installed, run:

   ```console
   ./scripts/publish.sh
   ```

   The script uses the repository's `.venv/bin/python` when available, otherwise
   `python3`; set `PYTHON` to select another interpreter. It builds through
   helpers in `scripts/helpers/`, which run identity checks, lint, tests, isolated builds,
   metadata checks, and a clean wheel installation, then uploads both artifacts.
   If `dist/<version>/` already exists, it reuses those prepared artifacts after
   checking their metadata. New commits advance the version;
   existing artifacts are not rebuilt automatically.

   To prepare artifacts without publishing, run `./scripts/publish.sh --prepare`.

4. A Git tag is not required by PyPI. It is strongly recommended for source
   provenance: tag the release commit as `v<version>`, push that tag, and create
   a corresponding GitHub Release.
5. Install the published version in a clean environment and run `hlsync --version`
   before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, create another commit (an empty release-retry
commit is sufficient) and build a new release; do not reuse the failed version.
Publish from one release history: separate branches can compute the same
version and are not separate publication streams.

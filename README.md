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

Or install it with pip:

```console
pip install hook-line-sync
```

The FTPS server must support explicit TLS with protected data connections
(`AUTH TLS` and `PROT P`) plus MLSD directory listings. Push additionally
requires MFMT and MDTM to apply and verify uploaded-file timestamps.

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
hlsync diff -r
hlsync push
```

`create` proposes the current directory as the local root; pressing Enter accepts
it. Declining prompts for another local folder. Use `--local-root PATH` to
provide one directly. Bare `push` is recursive, so `diff -r` is its matching
preview.

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

Global rules live in `~/.hlsync/rules.json`, apply to every profile, and are
created with a conservative metadata-only policy:

```text
**/.git/**
**/.svn/**
**/.hg/**
**/.DS_Store
**/Thumbs.db
**/desktop.ini
```

Manage global exclusions and inclusions from any directory with `-g` /
`--global`. Global operands are reusable patterns rooted at every profile's
local root; append `/` to target a complete directory tree:

```console
hlsync rules -e -g --pattern '*.tmp'
hlsync rules -i -g --pattern 'public/*.tmp'
hlsync rules -g                    # inspect global rules
hlsync rules -g --remove g4        # remove global rule g4
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

| Command | No path | Explicit directory | With `-r` |
| --- | --- | --- | --- |
| `list` / `list --remote` | Current directory, one level | Directory contents, one level | Include descendants |
| `diff` | Current directory, one level | Directory contents, one level | Include descendants |
| `push` | Complete current subtree | Directory contents, one level | Include descendants |
| `pull` | Error: path required | Directory contents, one level | Include descendants |

`.` explicitly selects the current directory. An immediate child directory
outside the traversal depth appears with `▸` but is diagnostic-only: it is not
created, replaced, deleted, or entered. The selected directory itself may be
created when selected files require it as their parent. An explicitly selected
remote-only directory is the deletion target itself, so push enumerates that
remote subtree and removes its contents deepest-first.

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

Remote listing connects read-only. Remote-excluded paths use `r x` and their
directories are shown as boundaries without being entered.

Directories appear before files at each level, with each group sorted by name.
Directories end in `/`; excluded paths use `x`. `-i`, `--inc`, and
`--included-only` hide excluded paths. `hlsync ls` remains an unadvertised
compatibility spelling.

## Diff

`diff` is read-only and shows what the corresponding push would do:

```console
hlsync diff
hlsync diff templates
hlsync diff templates -r
hlsync diff index.html app.js styles.css
hlsync diff '**/*.css'
```

Local path existence is authoritative except at explicit remote-exclusion
boundaries. In the default push view, remote-only
paths are shown as deletions because push will make the selected remote scope
match local state. Preview retention instead with:

```console
hlsync diff --keep-remote
hlsync diff -k
```

`--pull` changes the perspective for changed existing files and retains
remote-only paths. Diff normally shows actionable differences, retained
one-sided paths, conflicts, and local or remote exclusion boundaries. Use
`-i`/`--inc`/`--included-only` to hide exclusions. Use `-a`/`--all` to restore
unchanged and untraversed entries for the complete exploratory view.

For push authority, a locally excluded file is treated as absent. If it exists
remotely, default diff marks its deletion as `r -`; `diff -k --all` marks the
retained remote copy as `r !`. An excluded directory is instead a hard
traversal boundary and is retained remotely as `r !`. `-i` never hides an
actionable deletion.

Bare diff keeps traversal shallow but projects the recursive scope of bare
push: an immediate remote-only directory appears as `r - folder/ ▸`, warning that
push will delete the subtree while indicating that diff did not enumerate its
contents. Use `diff -r` to inspect beneath it. An explicit shallow operand such
as `diff .` retains an unentered child directory as `r   folder/ ▸`.

Show the current status and directory notation without connecting:

```console
hlsync --legend
```

Diff prints each directory as it is compared. For a shell-driven review,
`--paged` prints one directory, exits, and provides the exact stateless
`--resume` command for the next deterministic directory.

Colors are automatic on terminals, disabled for pipes and redirection, and
suppressed when `NO_COLOR` is set. Text markers retain the core meaning without
color. The left status column uses `l` and `r` for the relevant side; the right
column shows the action. Notably, `r x` is a remote-excluded path left
untouched, while `l x` and `r !` describe locally excluded paths that are
respectively absent or present remotely.

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
traversed or changed. Push deletes selected remote-only paths by default,
including remote copies of locally excluded files. Excluded directories on
either side are retained and never entered; an explicit local inclusion beneath
an excluded local directory is the only reason to enter that local boundary.
`-k` / `--keep-remote` retains remote-only paths. An included local directory
remains shallow unless `-r` is supplied. An explicitly selected remote-only
directory is fully enumerated because deleting that directory requires deleting
its contents. Bare `push` remains recursive by definition.

Preview the exact push scope and operation order without changing either side:

```console
hlsync push --dry
hlsync push templates --dry
hlsync push templates -r --dry
```

Unlike bare `diff`, bare `push --dry` inherits push's recursive default. It
also honors `-k`, remote exclusions, and explicit directory depth exactly as a
real push would. Interrupted-upload recovery is projected and reported but not
performed.

Dry and live push identify each local and remote directory as they scan it. A
parent is fully classified before HLSync enters eligible children, and excluded
directories are never entered.

Transfers print `Adding`, `Updating`, `Creating`, or `Deleting` with the path
immediately before each operation begins, then finish with a compact count.
When no operation is needed, HLSync prints `Nothing to push` or `Nothing to
pull` without announcing an empty transfer phase. An empty push also reports
how many included files are up to date in the selected scope. A push that
uses `--keep-remote` confirms retention without
repeating the paths already available through `diff`.

Retain remote-only paths for an exceptional push with:

```console
hlsync push --keep-remote
hlsync push -k 'generated/*.html'
```

Deletion is limited to the selected scope, runs only after every upload
succeeds, and is suppressed after any upload failure. Pull never deletes remote
paths.

### Safe file replacement

HLSync never uploads directly over a live destination. A direct FTP upload can
truncate or expose a partial live file when the connection fails. Instead,
HLSync:

1. Uploads to a uniquely named staging file beside the destination.
2. Verifies its size.
3. Applies the local whole-second UTC timestamp with MFMT and independently
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

Use `hlsync help [command]`, `hlsync --version`, and `hlsync --legend` for
built-in reference.

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

The PyPI distribution is `hook-line-sync`; the installed command and Python
package are both `hlsync`. See [`TODO.md`](TODO.md) for the
ordered work queue and [`CHANGELOG.md`](CHANGELOG.md) for completed changes.

Maintainer release instructions are in [`RELEASING.md`](RELEASING.md). The
self-contained PHP 8.3 project site is in [`website/`](website/README.md).
Releases use `0.<month>.<day>.<increment>` without leading zeroes; the increment
starts at `1` each day.

# Hook Line Sync

Hook Line Sync (`hlsync`) is a command-line workflow for deploying local
projects to shared hosting over explicit FTP over TLS (FTPS): map once, preview
the diff, then push the intended files.

HLSync is in pre-alpha development. Configuration, rules, local listings,
remote comparison, push, pull, and release packaging are implemented. See
[`TODO.md`](TODO.md) for upcoming work and [`CHANGELOG.md`](CHANGELOG.md) for
completed changes.

## Requirements and installation

- Python 3.10 or newer.
- Explicit FTPS with protected data connections (`AUTH TLS` and `PROT P`).
- MLSD for structured remote listings.
- For push, MFMT and MDTM to apply and verify uploaded-file timestamps.

For development:

```console
python -m pip install -e '.[dev]'
pytest
```

The PyPI distribution is `hook-line-sync`, the installed command is `hlsync`,
and the internal Python package remains `hls`. After the first PyPI release:

```console
python -m pip install hook-line-sync
```

## Quick start

HLSync reads credentials from environment variables. The defaults are:

```text
PROD_FTPS_USERNAME
PROD_FTPS_PASSWORD
```

From the local project root:

```console
hlsync add prod --host ftp.example.com --remote-root /public_html/site
hlsync connect
hlsync exclude .git node_modules
hlsync diff -r
hlsync push
```

`add` proposes the current directory as the local root; pressing Enter accepts
it. Bare `push` is recursive, so `diff -r` is its matching preview.

## Profiles and mapping

A profile identifies one deployment target: protocol, host, port, remote root,
credential environment-variable names, and one optional local root. Multiple
profiles may use the same server. Credential values are never stored in
`~/.hls/configs.json`.

FTPS is the default and currently the only protocol. Override credential
variable names when adding a profile if needed:

```console
hlsync add staging \
  --host ftp.example.com \
  --remote-root /public_html/staging \
  --username-env STAGING_FTPS_USERNAME \
  --password-env STAGING_FTPS_PASSWORD
```

If mapping was declined during `add`, map the current directory later:

```console
hlsync map staging
```

HLSync stores the canonical absolute local root and maps every descendant to
the same relative path under the remote root. Roots may not overlap across
profiles. Remapping requires confirmation and defaults to no.

The current directory selects the containing profile automatically:

```console
hlsync profiles          # all profiles; * marks the current one
hlsync profile           # current profile details
hlsync profile staging   # named profile details
hlsync connect            # verify FTPS, then disconnect
hlsync remove staging    # remove local configuration only
```

Use `--project <name>` where supported when running outside a mapped root.

## Synchronization rules

Exclude current paths permanently:

```console
hlsync exclude .git node_modules composer.json composer.lock
hlsync exc '*.md'
```

Normal wildcard operands are expanded against the current local tree and
recorded as exact paths. Quote them so the shell does not reject or alter them;
quoted and shell-expanded matches produce the same path rules.

Use `--pattern` when future matching paths should also be covered:

```console
hlsync exc --pattern '*.md'       # this directory only
hlsync exc --pattern '**/*.log'   # every directory below this point
hlsync inc --pattern 'vendor/**'  # re-include a subtree
```

`*` matches within one path segment; a complete `**` segment crosses directory
levels. Patterns are rooted where the command runs. HLSync rules are not
Gitignore syntax: `!`, `?`, bracket patterns, absolute paths, parent traversal,
and partial-segment `**` are rejected.

Rules have stable IDs and the highest matching ID wins. HLSync removes provably
redundant exact rules but preserves ambiguous wildcard overlaps.

```console
hlsync exc                 # exclusion rules
hlsync inc                 # inclusion rules
hlsync rules               # complete policy
hlsync rules remove 3
```

Multiple operands and comma-separated groups are accepted. A literal filename
containing a comma cannot be addressed because commas delimit groups.

## Paths and traversal

Paths are relative to the current directory inside the mapped root. Multiple
paths and wildcard patterns form one deterministic selection. Absolute paths,
parent traversal, and paths escaping the mapped root are rejected.

| Command | No path | Explicit directory | With `-r` |
| --- | --- | --- | --- |
| `list` | Current directory, one level | Directory contents, one level | Include descendants |
| `diff` | Current directory, one level | Directory contents, one level | Include descendants |
| `push` | Complete current subtree | Directory contents, one level | Include descendants |
| `pull` | Error: path required | Directory contents, one level | Include descendants |

`.` explicitly selects the current directory. An immediate child directory
outside the traversal depth appears with `▸` but is diagnostic-only: it is not
created, replaced, deleted, or entered. The selected directory itself may be
created when selected files require it as their parent.

## Local listing

`list` reads only the local filesystem, includes dotfiles, and applies the
configured rules:

```console
hlsync list
hlsync list templates
hlsync list '*.md'
hlsync list -r
hlsync list -r -i
```

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

Local path existence is authoritative. Remote-only paths are retained by
default rather than restored or deleted. Preview explicit remote deletion with:

```console
hlsync diff --prune-remote
```

`--pull` changes the perspective for changed existing files. Pull rejects
remote pruning. Diff shows unchanged and excluded entries by default;
`-i`/`--inc`/`--included-only` hides exclusions.

For push authority, an excluded local path is treated as absent. If it exists
remotely, ordinary diff marks it `!`; `diff -p` projects its deletion as `-`.

Show the current status and directory notation without connecting:

```console
hlsync --legend
```

Diff prints each directory as it is compared. For a shell-driven review,
`--paged` prints one directory, exits, and provides the exact stateless
`--resume` command for the next deterministic directory.

Colors are automatic on terminals, disabled for pipes and redirection, and
suppressed when `NO_COLOR` is set. Text markers retain the core meaning without
color; notably, `x` means excluded and absent remotely, while `!` means excluded
and present remotely.

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
changed existing local files but never restores a missing local path. Excluded
paths are never uploaded or pulled. A remote copy of an excluded path is
retained normally and becomes pruneable only with explicit `-p` authorization.
Pruning does not add traversal depth: an explicit directory remains shallow
unless `-r` is supplied. Bare `push` remains recursive by definition.

Transfers print `Adding`, `Updating`, `Creating`, or `Deleting` with the path
immediately before each operation begins, then finish with a compact count.
When no operation is needed, HLSync prints `Nothing to push` or `Nothing to
pull` without announcing an empty transfer phase. An empty push also reports
how many included files are up to date in the selected scope. A push that
retains remote-only paths points to `-p` for explicit deletion without
repeating the paths already available through `diff`.

Remote-only paths remain untouched unless a push explicitly authorizes pruning:

```console
hlsync push --prune-remote
hlsync push -p 'generated/*.html'
```

Pruning is limited to the selected scope, runs only after every upload succeeds,
and is suppressed after any upload failure. Pull never deletes remote paths.

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

Before every push, HLSync recovers its exact reserved artifacts in the selected
scope. Abandoned upload files are deleted; obsolete backups are deleted when
their destination exists; a sole backup is restored when its destination is
missing. This cleanup never requires `-p` and does not affect ordinary
remote-only files. Concurrent pushes to one profile are not supported.

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

## License and maintenance

HLSync is available under the [MIT License](LICENSE) for personal and commercial
use. A future voluntary Business subscription may fund development and provide
support or services; it is not required for commercial use.

Maintainer release instructions are in [`RELEASING.md`](RELEASING.md). The
self-contained PHP 8.3 project site is in [`website/`](website/README.md).
Releases use `0.<month>.<day>.<increment>` without leading zeroes; the increment
starts at `1` each day.

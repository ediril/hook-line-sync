# Hook Line Sync

Hook Line Sync (`hls`) is a Python CLI for transferring files between mapped
local folders and remote servers over explicit FTP over TLS (FTPS).

The project is in pre-alpha development. Configuration, connection, mapping,
tree inventory, comparison, and file transfer are available. Release packaging
remains on the work queue in [`TODO.md`](TODO.md).

## Requirements

- Python 3.10 or newer
- An FTPS server supporting explicit TLS (`AUTH TLS`) and protected data
  connections (`PROT P`)
- MLSD support for structured remote directory listings

## Development installation

```console
python -m pip install -e '.[dev]'
pytest
```

## Projects

Add a project with its FTPS endpoint and absolute remote root:

```console
hls add prod --host ftp.example.com --remote-root /public_html/site
```

FTPS is the default and currently the only implemented protocol. The explicit
form is `--protocol ftps`; unsupported protocols are rejected.

Each project owns its connection details, remote root, and local-root mapping.
Multiple projects may use the same server. Unless overridden, every project
reads credentials from:

```text
PROD_FTPS_USERNAME
PROD_FTPS_PASSWORD
```

Custom names can be supplied with `--username-env` and `--password-env`.
Credential values are never written to `~/.hls/configs.json`.

Verify a project's FTPS connection:

```console
hls connect prod
```

From anywhere under a mapped local root, the project name can be omitted:

```console
hls connect
```

An explicit name takes precedence. The command verifies authentication, the
configured remote root, and protected data-channel setup, then closes the
connection. It does not create a persistent session.

Remove a project and its locally stored mapping:

```console
hls remove prod
```

Removal does not connect to the server or delete remote files.

Command names may be shortened to any unique prefix. For example, `hls con`
means `hls connect`, while `hls comp` means `hls compare`. An ambiguous prefix
is rejected and lists its candidates. The established `ls`, `lsl`, `lsr`, and
`cmp` spellings remain available.

List everything currently configured and mark the project whose local root
contains the current directory:

```console
hls list
hls ls
```

`hls list projects` is the explicit form.

## Local roots

From the root of a local project, map its entire relative hierarchy to the
project's remote root:

```console
cd ~/Sites/my-site
hls map prod
```

The current directory is canonicalized and persisted as the project's single
local root. Every relative path underneath it maps to the same relative path
under the remote root. Local roots may not overlap across projects, so future
push and pull commands can determine the project and remote subdirectory from
the current directory without ambient state.

Persist exclusions after mapping with one quoted, comma-separated list of
gitignore-style wildcard patterns:

```console
hls exclude '.git/,node_modules/,*.log,**/.cache/'
hls exc '*.bak'
```

Re-include narrower paths later by appending an ordered override:

```console
hls include 'node_modules/required-package/dist/**'
hls inc 'var/generated/index.html'
```

The project is inferred from the current directory; use `--project <name>`
elsewhere. Patterns are relative to the local root and evaluated in command
order, so a later rule overrides an earlier matching rule. Excluded paths stay
outside tree listings, push, pull, and remote pruning, but compare displays
excluded files as neutral gray diagnostic entries. Empty patterns, `..`
traversal, and direct `!` input are rejected; `include` records the negation
internally. Commas cannot be used inside a pattern.

## Tree inventories

From anywhere under a mapped local root, list the complete local or remote
project tree:

```console
hls list local
hls list remote
hls lsl
hls lsr
```

`hls lsl` and `hls lsr` are shorthands for the corresponding `list` commands.

An explicit project may be supplied when running elsewhere:

```console
hls list local prod
hls list remote prod
```

Both commands display deterministic project-relative paths and apply the same
mapping exclusions. Directories, files, and symlinks are labeled separately;
symlinks are listed but never followed. Remote traversal uses MLSD over the
protected FTPS data connection and fails if the server cannot provide a
structured listing.

## Compare

Preview what a full-project push would do without changing either side:

```console
hls compare
hls cmp
```

Use the pull projection when needed:

```console
hls compare --pull
```

Limit the projection to one or more paths or wildcard patterns relative to the
current directory:

```console
hls compare index.html
hls compare index.html app.js styles.css
hls compare *
hls compare 'src/*.js'
hls compare '**/*.css'
```

An unquoted wildcard may be expanded by the shell into multiple arguments; HLS
treats them as one union. Directories included by that expansion do not cause
recursion. Quote a wildcard when HLS should interpret it itself. `*` stays
within one path segment and `**` matches recursively. A selection whose entire
union is unmatched or excluded, or that contains an absolute or
parent-traversing path, is rejected. Use
`--project <name>` to select a project explicitly; outside that project's local
root, its selectors are project-root-relative.

Selectors are applied before local and remote snapshots are built. HLS descends
only into directories that can contain a match: `*` scans the corresponding
directory without recursion, while `**` permits recursive traversal.

Compare uses a compact, perspective-relative status column:

```text
+  present only on the selected side
~  present on both sides but modified
-  missing from the selected side
!  type or symlink conflict
·  excluded from synchronization
```

The default selected side is local; `--pull` reverses it to remote. Status lines
are green, yellow, red, and magenta on terminals. Color is disabled when output
is redirected or `NO_COLOR` is set; excluded entries are gray. Color can be
controlled explicitly with
`--color auto|always|never`.

Compare uses diagnostic snapshots that inspect excluded directories so their
files can be shown. Push and pull continue to omit excluded paths entirely.
Selectors are still applied before traversal, so a path-limited comparison does
not scan unrelated excluded branches.

Local path existence remains authoritative for transfer behavior, so a
remote-only path is skipped rather than restored or deleted by default. Include
its remote deletion in the projected plan explicitly with:

```console
hls compare --prune-remote
hls cmp --pull -p
```

When a selector is present, pruning is strictly limited to matching remote-only
files.

File identity uses size and modification timestamps normalized to the coarser
precision reported by the local filesystem and remote MLSD facts. Identical
paths are omitted from the output.

Compare prints immediately flushed progress milestones to stderr while it
connects and scans. The final status view is written to stdout, so it can be
redirected without mixing status messages into the result.

## Push and pull

Apply the complete push or pull projection from anywhere inside a mapped
project:

```console
hls push
hls pull
```

Limit execution with the same selection syntax used by compare:

```console
hls push index.html
hls push index.html app.js styles.css
hls push *
hls push 'src/*.js'
hls pull '**/*.css'
```

Use `--project <name>` outside a mapped project. Push uploads local-only files
and replaces changed remote files. Pull replaces changed local files, but it
does not restore remote-only files because missing local paths are treated as
intentional deletions.

Remote-only paths are reported and left untouched unless pruning is explicitly
authorized:

```console
hls push --prune-remote
hls pull -p 'generated/*.html'
```

Pruning is limited by the selector and occurs only after all uploads or
downloads succeed. Remote uploads use temporary files and recoverable backups;
local downloads use atomic replacement. Type conflicts and symlinks abort the
entire plan before mutation. Each file replacement is atomic, but FTPS cannot
provide a transaction across the complete project, so an operation that fails
later does not roll back earlier completed files.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

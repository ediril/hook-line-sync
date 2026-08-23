# Hook Line Sync

Hook Line Sync (`hls`) is a Python CLI for transferring files between mapped
local folders and remote servers over explicit FTP over TLS (FTPS).

The project is in pre-alpha development. Configuration, connection, mapping,
tree inventory, comparison, file transfer, and release packaging are available.
Future work is ordered in
[`TODO.md`](https://github.com/ediril/hook-line-sync/blob/main/TODO.md), and
completed work is recorded in the
[`CHANGELOG.md`](https://github.com/ediril/hook-line-sync/blob/main/CHANGELOG.md).

## License and sustainability

HLS is released under the
[MIT License](https://github.com/ediril/hook-line-sync/blob/main/LICENSE).
Personal and commercial use are both permitted without payment.

A voluntary Business subscription is planned for professional users who want
to fund continued development and receive additional services or support. It
will not be required for commercial use of the MIT-licensed software.

The initial Business Support offering will be cancellable monthly and scoped
per organization. It will include private installation and configuration help,
review of one HLS deployment setup, compatibility troubleshooting, and priority
triage of reproducible defects. Response and resolution times will not be
guaranteed until a formal service-level plan is offered. Pricing and the
subscription channel will be announced separately.

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

The release distribution is named `hook-line-sync`; the installed command and
Python package are both named `hls`. Once the first release is published to
PyPI, installation will be:

```console
python -m pip install hook-line-sync
```

Maintainer release instructions are in
[`RELEASING.md`](https://github.com/ediril/hook-line-sync/blob/main/RELEASING.md).

The deployable PHP 8.3 project website lives in [`website/`](website/README.md).
That directory is self-contained and can be used directly as an Apache document
root on shared hosting.

## Projects

Add a project with its FTPS endpoint and absolute remote root:

```console
hls add prod --host ftp.example.com --remote-root /public_html/site
```

`hls add` proposes the current directory as the project's local root. Yes is
the default: press Enter to map it immediately, or decline to save the project
without a mapping. The project is not saved if that local root overlaps another
project.

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
means `hls connect`, while `hls d` means `hls diff`. An ambiguous prefix is
rejected and lists its candidates. The established `ls` compatibility spelling
remains available but is intentionally omitted from the help menu; `lsl` and
`lsr` remain documented commands.

Every path-accepting command supports multiple operands and comma-separated
groups. Diff, push, and pull interpret wildcards as selectors and use no
operands for the whole project. Exclude and include resolve wildcard operands
to current local paths by default, use `--pattern` to retain wildcards, and use
no operands to list their rules.

List everything currently configured and mark the project whose local root
contains the current directory:

```console
hls list
hls ls
```

`hls list projects` is the explicit form.

## Local roots

If mapping was declined during `hls add`, run `hls map` later from the root of
the local project:

```console
cd ~/Sites/my-site
hls map prod
```

The current directory is canonicalized and persisted as the project's single
local root. Every relative path underneath it maps to the same relative path
under the remote root. Local roots may not overlap across projects, so future
push and pull commands can determine the project and remote subdirectory from
the current directory without ambient state. If the project is already mapped,
`hls map` shows the existing and proposed roots and requires confirmation before
replacing the mapping; no is the default. Existing relative synchronization
rules are retained when the root changes.

Persist exclusions after mapping by naming local paths:

```console
hls exclude .git node_modules
hls exc '*.md'
hls exc composer.*
```

Operands are relative to the current directory within the project. HLS expands
quoted wildcards against the current local tree before recording exact paths,
so `hls exc *.md` and `hls exc '*.md'` have the same effect. A literal or
expanded directory means its complete subtree.

Use `--pattern` only when the rule itself should remain a reusable wildcard:

```console
hls exc --pattern '*.md'
hls exc --pattern '**/*.log'
```

In pattern mode, `*` matches within one directory level and `**` crosses
directory levels. Quoting is still necessary so the shell passes the wildcard
to HLS rather than expanding it first.

Each rule receives a stable numeric ID. Omit patterns to inspect the rules
recorded by each command:

```console
hls exc
hls inc
```

`hls exc` lists exclusion rules and `hls inc` lists inclusion rules, one per
line. Exact project-relative paths display with a `./` prefix, while reusable
wildcard patterns display as their stored expressions. Display the complete
ordered policy with:

```console
hls rules
```

A later matching rule wins. Adding the exact same normalized pattern again
automatically replaces its earlier rule, even when its action changes. Remove
any other unwanted rule by its stable ID:

```console
hls rules remove 3
```

List the local files currently eligible for synchronization with:

```console
hls tracked
```

`hls tracked` prints one regular-file path per line, inspects only the mapped
local root, and does not connect to FTPS. Use `--project <name>` when outside its
mapped root. Excluded files remain visible as gray diagnostics in `hls diff`.

Re-include narrower paths later by appending an ordered override:

```console
hls include node_modules/required-package/dist
hls inc var/generated/index.html
```

Use pattern mode for a reusable recursive inclusion:

```console
hls inc --pattern 'vendor/**'
```

Whether the shell or HLS expands a normal wildcard operand, HLS records the
matching visible paths. Child directories become recursive `/**` rules, while
files become exact paths. Multiple arguments and comma-separated groups can be
combined in one command. A literal filename containing a comma cannot be
addressed because commas delimit pattern groups.

The project is inferred from the current directory; use `--project <name>`
elsewhere. Excluded paths stay outside tree listings, push, pull, and remote
pruning, but diff displays excluded files as neutral gray diagnostic entries.
Empty patterns, absolute paths, parent traversal, and partial-segment `**` are
rejected. A quoted wildcard operand that matches nothing is rejected unless
`--pattern` is used.

Rules are stored as explicit `id`, `action`, and `pattern` records. HLS does not
store Gitignore lines, and `!` or a leading `/` has no special rule meaning.
Configuration schema version 7 is intentionally incompatible with the earlier
raw `exclusions` array; recreate projects and rules rather than reusing that
array.

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

## Diff

Preview what a full-project push would do without changing either side:

```console
hls diff
```

Use the pull projection when needed:

```console
hls diff --pull
```

Limit the projection to one or more paths or wildcard patterns relative to the
current directory:

```console
hls diff index.html
hls diff index.html app.js styles.css
hls diff 'index.html,app.js,styles.css'
hls diff *
hls diff 'src/*.js'
hls diff '**/*.css'
```

An unquoted wildcard may be expanded by the shell into multiple arguments; HLS
treats them as one union. Selected directories appear as entries, but their
contents are not scanned unless the selector is recursive. Quote a wildcard
when HLS should interpret it itself. `*` stays within one path segment and `**`
matches recursively. A selection whose entire union is unmatched or excluded,
or that contains an absolute or parent-traversing path, is rejected. Use
`--project <name>` to select a project explicitly; outside that project's local
root, its selectors are project-root-relative.

Selectors are applied before local and remote snapshots are built. HLS descends
only into directories that can contain a match: `*` scans the corresponding
directory without recursion, while `**` permits recursive traversal.

Diff uses compact, perspective-relative status and type columns. Directories
receive `d`; files and symlinks leave the type column blank:

```text
+ d new-directory
+   new-file
~   modified on the selected side
-   missing from the selected side
!   type or symlink conflict
·   excluded from synchronization
```

The default selected side is local; `--pull` reverses it to remote. Status lines
are green, yellow, red, and magenta on terminals. Color is disabled when output
is redirected or `NO_COLOR` is set. Directory paths are bright blue, excluded
directory paths are darker blue, and excluded non-directories are gray. Color
can be controlled explicitly with `--color auto|always|never`.

Diff uses diagnostic snapshots that show excluded directories and inspect them
so their contents can be shown. Push and pull continue to omit excluded paths entirely.
Selectors are still applied before traversal, so a path-limited comparison does
not scan unrelated excluded branches.

Local path existence remains authoritative for transfer behavior, so a
remote-only path is skipped rather than restored or deleted by default. Include
its remote deletion in the projected plan explicitly with:

```console
hls diff --prune-remote
hls diff --pull -p
```

When a selector is present, pruning is strictly limited to matching remote-only
files.

File identity uses size and modification timestamps normalized to the coarser
precision reported by the local filesystem and remote MLSD facts. Identical
paths are omitted from the output.

Diff prints immediately flushed progress milestones to stderr while it
connects and scans. The final status view is written to stdout, so it can be
redirected without mixing status messages into the result.

## Push and pull

Apply the complete push or pull projection from anywhere inside a mapped
project:

```console
hls push
hls pull
```

Limit execution with the same selection syntax used by diff:

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

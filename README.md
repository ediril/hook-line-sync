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
for `list` remains available but is intentionally omitted from the help menu.

Every path-accepting command supports multiple operands and comma-separated
groups. List, diff, push, and pull interpret wildcards as selectors and use no
operands for the current directory's immediate contents; add `-r` to include
the current subtree. Exclude and include resolve wildcard operands to current
local paths by default, use `--pattern` to retain wildcards, and use no operands
to list their rules.

List every configured profile and mark the one whose local root
contains the current directory:

```console
hls profiles
```

The active profile is marked with `*`; other profile names are printed without
connection details. Inspect the current profile inferred from the working
directory, or name one explicitly from anywhere:

```console
hls profile
hls profile staging
```

The detail view shows protocol, host and port, local and remote roots,
credential environment-variable names, and the number of synchronization
rules. It never displays credential values; use `hls rules` to inspect the
rules themselves.

When a command prefix matches more than one command, an interactive terminal
lists the candidates and requires a numbered choice with no default. A
noninteractive invocation fails with the candidate list instead of waiting for
input or guessing, which keeps scripts safe.

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

`hls exc` lists exclusion rules and `hls inc` lists inclusion rules. Rules are
grouped beneath the nearest literal folder and sorted by name. Patterns that can
apply beneath any folder appear under `Everywhere`. Display the complete policy
with:

```console
hls rules
```

A higher matching rule ID wins. Adding the exact same normalized pattern again
removes its earlier rule. If the remaining policy already includes or excludes
the path as requested, HLS does not add a redundant replacement; otherwise the
new action receives a new ID. HLS leaves more complex wildcard overlaps intact
rather than guessing that they are equivalent. Remove any unwanted rule by its
stable ID:

```console
hls rules remove 3
```

List the current local directory and its exclusion status with:

```console
hls list
hls list *
hls list .
hls list templates
hls list --recursive
```

With no operands, `hls list` performs its own one-level selection, so dotfiles
are included without relying on shell wildcard behavior. `.` has the same
one-level meaning. Add `-r` or `--recursive` to include every descendant under
the current directory. Explicit path and wildcard operands retain the shared
selector syntax. A selected file is listed directly; a selected directory acts
as a container, so `hls list templates` lists the immediate children of
`templates` without requiring `templates/*`. Add `-r` to include all descendants
of selected directories. Bare `*` continues to be expanded by the shell, while
quoted patterns are interpreted by HLS.

Listings use file-browser order at every displayed level: directories first by
name, followed by files by name.

The command does not connect to FTPS. Directories use a `d` type marker and
excluded paths use `x`; included files leave both columns blank. Use
`--project <name>` outside a mapped root, where selection starts at the mapped
root. On terminals, included directories are bright blue, excluded directories
are darker blue, and excluded files are gray. Use `--color auto|always|never`
to control coloring. `hls ls` remains an unadvertised compatibility spelling.

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
elsewhere. Excluded paths stay outside push, pull, remote pruning, and the
default diff; they remain visible in the local listing and in `hls diff --all`.
Empty patterns, absolute paths, parent traversal, and partial-segment `**` are
rejected. A quoted wildcard operand that matches nothing is rejected unless
`--pattern` is used.

Rules are stored as explicit `id`, `action`, and `pattern` records. HLS does not
store Gitignore lines, and `!` or a leading `/` has no special rule meaning.
Configuration schema version 7 is intentionally incompatible with the earlier
raw `exclusions` array; recreate projects and rules rather than reusing that
array.

## Diff

Preview what a push of the current directory's immediate contents would do
without changing either side:

```console
hls diff
```

Preview the complete current subtree explicitly:

```console
hls diff -r
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
hls diff .
hls diff templates
hls diff templates -r
```

An unquoted wildcard may be expanded by the shell into multiple arguments; HLS
treats them as one union. With no operands, diff selects the current directory's
immediate contents. An explicitly selected directory acts as a synchronization
container with the same one-level default. `-r` or `--recursive` extends either
scope through all descendants. `.` selects the current directory using the same
container rule. Quote a wildcard when HLS should interpret it itself. `*` stays
within one path segment and `**` matches recursively. A selection whose entire
union is unmatched or excluded, or that contains an absolute or parent-traversing
path, is rejected. Use
`--project <name>` to select a project explicitly; outside that project's local
root, its selectors are project-root-relative.

Selectors are applied before local and remote snapshots are built. HLS descends
only into selected directory containers and directories that can contain a
pattern match.

Diff uses compact, perspective-relative status and type columns. Directories
receive `d`; files and symlinks leave the type column blank:

```text
+ d new-directory
+   new-file
~   modified on the selected side
-   missing from the selected side
·   present on only one side but left untouched
?   type or symlink conflict
=   unchanged
x   excluded from synchronization
```

The default selected side is local; `--pull` reverses it to remote. By default,
diff prints synchronization actions, conflicts, and one-sided paths that will
be kept. Use `hls diff --all` to also show unchanged and excluded paths. Status
lines use distinct terminal
colors; unchanged and excluded paths are dimmed. Color is disabled when output
is redirected or `NO_COLOR` is set. Directory paths are bright blue, excluded
directory paths are darker blue, and color can be controlled explicitly with
`--color auto|always|never`.

Diff applies selectors before remote traversal and requests one MLSD listing per
relevant directory. Results are printed and flushed after each directory rather
than waiting for a complete remote snapshot. The default mode does not descend
into wholly excluded branches; `--all` does so to produce its complete audit
view. Push and pull continue to omit excluded paths entirely.

For an interruptible directory-by-directory review, use:

```console
hls diff --paged
```

Paged mode compares one directory, prints the exact resume command, and exits
to the shell. Running that command resumes at the printed project-relative
directory. Traversal is deterministic and the cursor is stateless: HLS stores
no paging session, though it must list the cursor's ancestor directories again
to reconstruct the remaining walk safely.

Local path existence remains authoritative for transfer behavior, so a
remote-only path is shown with `·` and skipped rather than restored or deleted
by default. Preview its deletion with `-` explicitly using:

```console
hls diff --prune-remote
```

When a selector is present, pruning is strictly limited to matching remote-only
files. Remote pruning belongs exclusively to the push direction, so
`hls diff --pull --prune-remote` is rejected.

File identity uses size and modification timestamps normalized to the coarser
precision reported by the local filesystem and remote MLSD facts. Identical
paths are omitted unless `--all` is supplied.

Diff prints immediately flushed progress to stderr while it connects and moves
through directories. Diff entries are progressively written to stdout, so they
can be redirected without mixing status messages into the result.
Within each displayed directory, subdirectories are sorted first by name and
files follow by name, matching `hls list`.

## Push and pull

Apply the push or pull projection for the current directory's immediate
contents:

```console
hls push
hls pull
```

Apply the complete current subtree projection explicitly:

```console
hls push -r
hls pull -r
```

Limit execution with the same selection syntax used by diff:

```console
hls push index.html
hls push index.html app.js styles.css
hls push *
hls push 'src/*.js'
hls pull '**/*.css'
hls push templates
hls push templates -r
```

No-argument push and pull use the same current-directory scope as diff:
immediate contents by default and the complete current subtree with `-r`.
Explicit directory operands follow the same container rule. This keeps every
scoped diff equal to the corresponding transfer plan.

Use `--project <name>` outside a mapped project. Push uploads local-only files
and replaces changed remote files. Pull replaces changed local files, but it
does not restore remote-only files because missing local paths are treated as
intentional deletions.

Remote-only paths are reported and left untouched unless pruning is explicitly
authorized on a push:

```console
hls push --prune-remote
hls push -p 'generated/*.html'
```

Pruning is limited by the selector and occurs only after all uploads succeed.
Pull never deletes remote paths. Remote uploads use temporary files and
recoverable backups; local downloads use atomic replacement. Type conflicts and
symlinks abort the entire plan before mutation. Each file replacement is atomic,
but FTPS cannot provide a transaction across the complete project, so an
operation that fails later does not roll back earlier completed files.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

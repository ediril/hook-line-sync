# Hook Line Sync

Hook Line Sync (`hls`) is a Python CLI for transferring files between mapped
local folders and remote servers over explicit FTP over TLS (FTPS).

The project is in pre-alpha development. The configuration, connection, and
local-root mapping foundation is available; file-transfer commands remain on
the work queue in [`TODO.md`](TODO.md).

## Requirements

- Python 3.10 or newer
- An FTPS server supporting explicit TLS (`AUTH TLS`) and protected data
  connections (`PROT P`)

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

The connection uses certificate verification and refuses plaintext fallback.

Remove a project and its locally stored mapping:

```console
hls remove prod
```

Removal does not connect to the server or delete remote files.

List everything currently configured and mark the project whose local root
contains the current directory:

```console
hls list
hls ls
```

`hls list projects` is the explicit form. The `list` command will later also
host local, remote, and diff file inventories.

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

Exclude paths with one quoted, comma-separated list of gitignore-style wildcard
patterns:

```console
hls map prod --exclude '.git/,node_modules/,*.log,**/.cache/'
```

Patterns are relative to the local root. Empty patterns, `..` traversal, and
gitignore re-inclusion patterns beginning with `!` are rejected. Commas cannot
be used inside a pattern.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

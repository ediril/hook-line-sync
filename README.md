# Hook Line Sync

Hook Line Sync (`hls`) is a Python CLI for transferring files between mapped
local folders and remote servers over explicit FTP over TLS (FTPS).

The project is in pre-alpha development. The configuration and connection
foundation is available; mapping and file-transfer commands remain on the work
queue in [`TODO.md`](TODO.md).

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
hls add prod ftps --host ftp.example.com --remote-root /public_html/site
```

Each project owns its connection details, remote root, and mappings. Multiple
projects may use the same server. By default, credential variable names are
derived from the project name. The command above reads credentials from:

```text
PROD_FTPS_USERNAME
PROD_FTPS_PASSWORD
```

Custom names can be supplied with `--username-env` and `--password-env`.
Credential values are never written to `~/.hls/configs.json`.

Select a project for the current directory tree:

```console
cd ~/Sites/my-site
hls use prod
hls use
```

The context is stored in `~/.hls/contexts.json`, keyed by canonical absolute
directory. Descendants inherit the nearest context. It can be removed from the
directory where it was set with:

```console
hls use --clear
```

Verify the active project's FTPS connection, or name another explicitly:

```console
hls connect
hls connect prod
```

The connection uses certificate verification and refuses plaintext fallback.
There is no global default project. An explicit project wins; otherwise a
command uses the nearest directory context and fails if none exists.

Remove a project and all of its locally stored mappings:

```console
hls remove prod
```

Removal does not connect to the server or delete remote files.

## Mappings

Bind an existing local folder to a directory relative to the project's remote
root:

```console
hls map ./site
hls map ./shared-assets static/assets
hls map ./site --project prod
```

The local folder may be relative or absolute, but its canonical absolute path is
always persisted. If the remote directory is omitted, it defaults to the
canonical local folder's basename. For example, `./site` maps to
`<remote-root>/site`. Use `.` explicitly as the remote directory to map directly
to the remote root.

Remote mapping directories must be relative and cannot contain `..`. Within one
project, neither side of a mapping may duplicate, contain, or be contained by
another mapping.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

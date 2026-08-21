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

Verify a project's FTPS connection explicitly:

```console
hls connect prod
```

The connection uses certificate verification and refuses plaintext fallback.
There is no global default project. File operations will resolve their project
through persisted mappings so ambient CLI state cannot redirect a transfer.

Remove a project and all of its locally stored mappings:

```console
hls remove prod
```

Removal does not connect to the server or delete remote files.

## Mappings

Bind an existing local folder to an absolute folder within a project's remote
root:

```console
hls map prod /public_html/site ./site
```

If the local folder is omitted, the current directory is used. Local paths are
resolved before storage, including symlinks. Within one project, neither side
of a mapping may duplicate, contain, or be contained by another mapping. A
remote mapping may not escape the project's configured remote root.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

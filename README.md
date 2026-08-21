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

## Configuration

Add a server profile:

```console
hls add prod ftps --host ftp.example.com
```

By default, credential variable names are derived from the profile name. The
command above reads credentials from:

```text
PROD_FTPS_USERNAME
PROD_FTPS_PASSWORD
```

Custom names can be supplied with `--username-env` and `--password-env`.
Credential values are never written to `~/.hls/configs.json`.

Verify a profile's FTPS connection explicitly:

```console
hls connect prod
```

The connection uses certificate verification and refuses plaintext fallback.
There is no global default profile. File operations will resolve their server
through persisted mappings so ambient CLI state cannot redirect a transfer.

## Mappings

Bind an existing local folder to an absolute folder in a server profile's FTP
namespace:

```console
hls map prod /public_html ./site
```

If the local folder is omitted, the current directory is used. Local paths are
resolved before storage, including symlinks. Within one profile, neither side
of a mapping may duplicate, contain, or be contained by another mapping.

## Versioning

Releases use `0.<month>.<day>.<increment>` without leading zeroes. The final
component starts at `1` each day and increments for additional releases on that
date.

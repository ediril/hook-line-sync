# Hook Line Sync MVP

`hls` is a Python CLI application that transfers files between local folders and
remote servers over explicit FTP over TLS (FTPS).

## Packaging

- The command is named `hls`.
- The application supports Python 3.10 and newer.
- The project is packaged with `pyproject.toml` and will be distributed through
  PyPI.
- Versions use `0.<month>.<day>.<increment>` without leading zeroes. The final
  component starts at `1` each day and increases for subsequent releases made
  that day.

## Server configurations

Add a named server configuration with:

```text
hls add <config-name> ftps
```

- Configuration names are non-empty CLI identifiers, such as `prod` or
  `client-a`.
- Connection metadata is persisted in `~/.hls/configs.json`.
- Passwords and username values are not persisted in the configuration file.
  Each server configuration instead records the environment-variable names
  from which its credentials are read.
- The production configuration uses `PROD_FTPS_USERNAME` and
  `PROD_FTPS_PASSWORD`.
- FTPS uses explicit TLS (`AUTH TLS`), verifies the server certificate, and
  protects the data connection (`PROT P`). There is no fallback to plaintext
  FTP.

Set the default server configuration with:

```text
hls set <config-name>
```

## Mappings

Add a local-to-remote mapping with:

```text
hls map <config-name> <remote-folder> [<local-folder>]
```

- If `<local-folder>` is omitted, the current directory is used.
- `<remote-folder>` is an absolute POSIX path within the authenticated server's
  FTP namespace.
- Mappings apply one-to-one and recursively to subfolders.
- Local paths are canonicalized before they are stored or compared.
- Within one server configuration, mappings may not overlap on either the local
  or remote side. An attempted duplicate, ancestor, or descendant mapping is an
  error.

## Operations

```text
hls upload <local-file> [<remote-file-name>]
hls upload <local-folder>/ [<remote-folder-name>]
hls upload <local-folder>/*.js
hls upload --diff [<filter>]

hls download <remote-file> [<local-file-name>]
hls download <remote-folder>/ [<local-folder-name>]
hls download --diff [<filter>]

hls list local
hls list remote
hls list diff
```

- The comparison behind `list diff` is initially based on file size and
  normalized modification timestamp.
- The MVP never deletes local or remote files.
- Transfer selection, comparison, and mapping logic remain independent of the
  FTPS implementation. FTPS is accessed through a transport interface so later
  transports do not require changes to the core model.

## Information commands

```text
hls help
hls version
```

Short aliases may be added when their behavior is unambiguous.

## Deferred details

The exact glob rules, rename constraints, timestamp precision policy, symlink
behavior, overwrite UX, and output formatting will be specified with the
commands that need them.

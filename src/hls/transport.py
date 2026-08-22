from __future__ import annotations

import ftplib
import os
import ssl
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Protocol

from hls.config import ProjectConfiguration
from hls.exclusions import ExclusionSpec
from hls.snapshot import EntryKind, TreeEntry, TreeSnapshot


class TransportError(RuntimeError):
    """Raised when a remote transport cannot be used safely."""


class RemoteTransport(Protocol):
    def connect(self) -> None: ...

    def snapshot(self, exclusions: ExclusionSpec) -> TreeSnapshot: ...

    def close(self) -> None: ...


@dataclass
class ExplicitFTPSTransport:
    configuration: ProjectConfiguration
    timeout: float = 30.0
    ssl_context: ssl.SSLContext | None = None

    def __post_init__(self) -> None:
        self._client: ftplib.FTP_TLS | None = None

    def connect(self) -> None:
        username = os.environ.get(self.configuration.username_env)
        password = os.environ.get(self.configuration.password_env)
        missing = [
            name
            for name, value in (
                (self.configuration.username_env, username),
                (self.configuration.password_env, password),
            )
            if value is None
        ]
        if missing:
            raise TransportError(
                f"missing credential environment variable(s): {', '.join(missing)}"
            )

        client = ftplib.FTP_TLS(
            context=self.ssl_context or ssl.create_default_context(),
            timeout=self.timeout,
        )
        try:
            client.connect(self.configuration.host, self.configuration.port)
            client.auth()
            client.login(username, password)
            client.prot_p()
            client.cwd(self.configuration.remote_root)
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            try:
                client.close()
            finally:
                raise TransportError(
                    f"could not open explicit FTPS project at "
                    f"{self.configuration.host}:{self.configuration.port}"
                    f"{self.configuration.remote_root}: {error}"
                ) from error
        self._client = client

    def close(self) -> None:
        if self._client is None:
            return
        client, self._client = self._client, None
        try:
            client.quit()
        except (OSError, ftplib.Error):
            client.close()

    def snapshot(self, exclusions: ExclusionSpec) -> TreeSnapshot:
        if self._client is None:
            raise TransportError("FTPS transport is not connected")
        entries: list[TreeEntry] = []

        def walk(relative_directory: PurePosixPath) -> None:
            remote_directory = relative_directory.as_posix()
            if remote_directory == ".":
                remote_directory = ""
            try:
                children = sorted(
                    self._client.mlsd(remote_directory, facts=["type"]),
                    key=lambda item: item[0],
                )
            except (OSError, ftplib.Error, ssl.SSLError) as error:
                display_path = remote_directory or "."
                raise TransportError(
                    f"could not list remote directory '{display_path}': {error}"
                ) from error

            for name, facts in children:
                entry_type = facts.get("type", "").lower()
                if entry_type in {"cdir", "pdir"}:
                    continue
                if not name or "/" in name or name in {".", ".."}:
                    raise TransportError(f"invalid name in remote listing: {name!r}")
                relative = relative_directory / name
                relative_path = relative.as_posix()
                if entry_type == "dir":
                    kind: EntryKind = "directory"
                elif entry_type == "file":
                    kind = "file"
                elif entry_type.startswith("os.unix=slink"):
                    kind = "symlink"
                else:
                    raise TransportError(
                        f"unsupported remote entry type {entry_type!r} "
                        f"for '{relative_path}'"
                    )
                if exclusions.excludes(
                    relative_path,
                    is_directory=kind == "directory",
                ):
                    continue
                entries.append(TreeEntry(relative_path, kind))
                if kind == "directory":
                    walk(relative)

        walk(PurePosixPath())
        return TreeSnapshot(tuple(entries))

    def __enter__(self) -> ExplicitFTPSTransport:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

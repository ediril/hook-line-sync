from __future__ import annotations

import ftplib
import os
import ssl
from calendar import timegm
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol
from uuid import uuid4

from hls.config import ProjectConfiguration
from hls.rules import RuleSet
from hls.selection import FileSelection
from hls.snapshot import EntryKind, SnapshotError, TreeEntry, TreeSnapshot


class TransportError(RuntimeError):
    """Raised when a remote transport cannot be used safely."""


class PathOperationError(TransportError):
    """Raised when one remote path fails but the FTPS session remains usable."""


def _parse_mlsd_modify(value: str, path: str) -> tuple[int, int]:
    base, separator, fraction = value.partition(".")
    if len(base) != 14 or not base.isdigit() or (
        separator and (not fraction or not fraction.isdigit())
    ):
        raise TransportError(
            f"invalid MLSD modify timestamp {value!r} for '{path}'"
        )
    try:
        timestamp = datetime.strptime(base, "%Y%m%d%H%M%S")
    except ValueError as error:
        raise TransportError(
            f"invalid MLSD modify timestamp {value!r} for '{path}'"
        ) from error
    fraction_digits = min(len(fraction), 9)
    fractional_ns = int(fraction[:9].ljust(9, "0")) if fraction else 0
    precision_ns = 10 ** (9 - fraction_digits) if fraction else 1_000_000_000
    return timegm(timestamp.timetuple()) * 1_000_000_000 + fractional_ns, precision_ns


def _relative_remote_path(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise TransportError(f"remote operation path must be relative: {value!r}")
    return path.as_posix()


class RemoteTransport(Protocol):
    def connect(self) -> None: ...

    def snapshot(
        self,
        rules: RuleSet,
        selector: FileSelection | None = None,
        *,
        include_excluded: bool = False,
    ) -> TreeSnapshot: ...

    def list_directory(
        self,
        relative_directory: PurePosixPath,
        rules: RuleSet,
    ) -> TreeSnapshot: ...

    def make_directory(self, relative_path: str) -> None: ...

    def upload_file(
        self,
        local_path: BinaryIO,
        relative_path: str,
        *,
        size: int,
        modified_ns: int,
        replace: bool,
    ) -> None: ...

    def download_file(self, relative_path: str, destination: BinaryIO) -> None: ...

    def delete_path(self, relative_path: str, *, is_directory: bool) -> None: ...

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

    def snapshot(
        self,
        rules: RuleSet,
        selector: FileSelection | None = None,
        *,
        include_excluded: bool = False,
    ) -> TreeSnapshot:
        if self._client is None:
            raise TransportError("FTPS transport is not connected")
        entries: list[TreeEntry] = []

        def walk(relative_directory: PurePosixPath) -> None:
            listing = self.list_directory(relative_directory, rules)
            for entry in listing.entries:
                relative_path = entry.path
                relative = PurePosixPath(relative_path)
                kind = entry.kind
                excluded = entry.excluded
                visible = not excluded or include_excluded
                selected = visible and (
                    selector is None or selector.matches(relative_path)
                )
                if selected:
                    entries.append(entry)
                selection_may_descend = (
                    selector is None
                    or selector.may_match_descendant(relative_path)
                )
                exclusion_may_descend = (
                    include_excluded
                    or not excluded
                    or rules.may_include_descendant(relative_path)
                )
                if (
                    kind == "directory"
                    and selection_may_descend
                    and exclusion_may_descend
                ):
                    walk(relative)

        walk(PurePosixPath())
        return TreeSnapshot(tuple(entries))

    def list_directory(
        self,
        relative_directory: PurePosixPath,
        rules: RuleSet,
    ) -> TreeSnapshot:
        """Read one remote directory using one structured MLSD listing."""
        client = self._connected_client()
        remote_directory = relative_directory.as_posix()
        if remote_directory == ".":
            remote_directory = ""
        try:
            children = sorted(
                client.mlsd(
                    remote_directory,
                    facts=["type", "size", "modify"],
                ),
                key=lambda item: item[0],
            )
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            display_path = remote_directory or "."
            raise TransportError(
                f"could not list remote directory '{display_path}': {error}"
            ) from error

        entries: list[TreeEntry] = []
        for name, facts in children:
            entry_type = facts.get("type", "").lower()
            if entry_type in {"cdir", "pdir"}:
                continue
            if not name or "/" in name or name in {".", ".."}:
                raise TransportError(f"invalid name in remote listing: {name!r}")
            relative_path = (relative_directory / name).as_posix()
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
            excluded = rules.excludes(
                relative_path,
                is_directory=kind == "directory",
            )
            if kind != "file":
                entries.append(TreeEntry(relative_path, kind, excluded=excluded))
                continue
            size_value = facts.get("size")
            modified_value = facts.get("modify")
            if size_value is None or modified_value is None:
                raise TransportError(
                    f"remote file metadata is incomplete for '{relative_path}'"
                )
            try:
                size = int(size_value)
            except ValueError as error:
                raise TransportError(
                    f"invalid MLSD size {size_value!r} for '{relative_path}'"
                ) from error
            modified_ns, precision_ns = _parse_mlsd_modify(
                modified_value,
                relative_path,
            )
            try:
                entries.append(
                    TreeEntry(
                        relative_path,
                        kind,
                        size=size,
                        modified_ns=modified_ns,
                        timestamp_precision_ns=precision_ns,
                        excluded=excluded,
                    )
                )
            except SnapshotError as error:
                raise TransportError(
                    f"invalid remote file metadata for '{relative_path}': {error}"
                ) from error
        return TreeSnapshot(tuple(entries))

    def _connected_client(self) -> ftplib.FTP_TLS:
        if self._client is None:
            raise TransportError("FTPS transport is not connected")
        return self._client

    def make_directory(self, relative_path: str) -> None:
        path = _relative_remote_path(relative_path)
        try:
            self._connected_client().mkd(path)
        except ftplib.error_perm as error:
            raise PathOperationError(
                f"could not create remote directory '{path}': {error}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            raise TransportError(
                f"could not create remote directory '{path}': {error}"
            ) from error

    def upload_file(
        self,
        local_path: BinaryIO,
        relative_path: str,
        *,
        size: int,
        modified_ns: int,
        replace: bool,
    ) -> None:
        path = _relative_remote_path(relative_path)
        remote = PurePosixPath(path)
        token = uuid4().hex
        temporary = str(remote.with_name(f".{remote.name}.hls-upload-{token}"))
        backup = str(remote.with_name(f".{remote.name}.hls-backup-{token}"))
        client = self._connected_client()
        timestamp = datetime.fromtimestamp(
            modified_ns // 1_000_000_000,
            tz=UTC,
        ).strftime("%Y%m%d%H%M%S")

        def discard(candidate: str) -> None:
            try:
                client.delete(candidate)
            except (OSError, ftplib.Error):
                pass

        try:
            client.storbinary(f"STOR {temporary}", local_path)
            uploaded_size = client.size(temporary)
            if uploaded_size != size:
                raise TransportError(
                    f"remote upload size mismatch for '{path}': "
                    f"expected {size}, got {uploaded_size}"
                )
            response = client.sendcmd(f"MFMT {timestamp} {temporary}")
            if not response.startswith(f"213 Modify={timestamp};"):
                raise TransportError(
                    f"remote server did not verify modification time for "
                    f"'{path}': {response}"
                )
            current_source = os.fstat(local_path.fileno())
            if (
                current_source.st_size != size
                or current_source.st_mtime_ns != modified_ns
            ):
                raise TransportError(
                    f"local source changed while staging remote file '{path}'"
                )
        except ftplib.error_perm as error:
            discard(temporary)
            raise PathOperationError(
                f"could not stage remote file '{path}': {error}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            discard(temporary)
            raise TransportError(
                f"could not stage remote file '{path}': {error}"
            ) from error

        if not replace:
            try:
                client.rename(temporary, path)
            except ftplib.error_perm as error:
                discard(temporary)
                raise PathOperationError(
                    f"could not install remote file '{path}': {error}"
                ) from error
            except (OSError, ftplib.Error, ssl.SSLError) as error:
                discard(temporary)
                raise TransportError(
                    f"could not install remote file '{path}': {error}"
                ) from error
            return

        try:
            client.rename(path, backup)
        except ftplib.error_perm as error:
            discard(temporary)
            raise PathOperationError(
                f"could not stage replacement of remote file '{path}': {error}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            discard(temporary)
            raise TransportError(
                f"could not stage replacement of remote file '{path}': {error}"
            ) from error
        try:
            client.rename(temporary, path)
        except ftplib.error_perm as error:
            discard(temporary)
            try:
                client.rename(backup, path)
            except (OSError, ftplib.Error, ssl.SSLError) as restore_error:
                raise TransportError(
                    f"could not install remote file '{path}' and could not "
                    f"restore its backup '{backup}': {restore_error}"
                ) from error
            raise PathOperationError(
                f"could not install remote file '{path}'; its prior version "
                f"was restored: {error}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            discard(temporary)
            try:
                client.rename(backup, path)
            except (OSError, ftplib.Error, ssl.SSLError) as restore_error:
                raise TransportError(
                    f"could not install remote file '{path}' and could not "
                    f"restore its backup '{backup}': {restore_error}"
                ) from error
            raise TransportError(
                f"could not install remote file '{path}'; its prior version "
                f"was restored: {error}"
            ) from error
        try:
            client.delete(backup)
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            raise TransportError(
                f"installed remote file '{path}' but could not remove backup "
                f"'{backup}': {error}"
            ) from error

    def download_file(self, relative_path: str, destination: BinaryIO) -> None:
        path = _relative_remote_path(relative_path)
        try:
            self._connected_client().retrbinary(f"RETR {path}", destination.write)
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            raise TransportError(
                f"could not download remote file '{path}': {error}"
            ) from error

    def delete_path(self, relative_path: str, *, is_directory: bool) -> None:
        path = _relative_remote_path(relative_path)
        try:
            client = self._connected_client()
            if is_directory:
                client.rmd(path)
            else:
                client.delete(path)
        except ftplib.error_perm as error:
            raise PathOperationError(
                f"could not delete remote path '{path}': {error}"
            ) from error
        except (OSError, ftplib.Error, ssl.SSLError) as error:
            raise TransportError(
                f"could not delete remote path '{path}': {error}"
            ) from error

    def __enter__(self) -> ExplicitFTPSTransport:
        self.connect()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

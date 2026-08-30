from __future__ import annotations

import ftplib
import os
import re
import ssl
from calendar import timegm
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import BinaryIO, Protocol
from uuid import uuid4

from hlsync.config import ProfileConfiguration
from hlsync.rules import RuleSet
from hlsync.selection import FileSelection
from hlsync.snapshot import EntryKind, SnapshotError, TreeEntry, TreeSnapshot


class TransportError(RuntimeError):
    """Raised when a remote transport cannot be used safely."""


class PathOperationError(TransportError):
    """Raised when one remote path fails but the FTPS session remains usable."""


_HLSYNC_ARTIFACT_NAME = re.compile(
    r"^\.(?P<destination>.+)\.hlsync-(?P<kind>upload|backup)-"
    r"(?P<token>[0-9a-f]{32})$"
)


@dataclass(frozen=True)
class _HLSyncArtifact:
    path: str
    destination: str
    kind: str


def _hlsync_artifact(path: str) -> _HLSyncArtifact | None:
    remote = PurePosixPath(path)
    match = _HLSYNC_ARTIFACT_NAME.fullmatch(remote.name)
    if match is None:
        return None
    destination = remote.with_name(match.group("destination")).as_posix()
    return _HLSyncArtifact(path, destination, match.group("kind"))


@dataclass(frozen=True)
class _ArtifactRecoverySelection:
    selected: FileSelection

    @property
    def pattern(self) -> str:
        return self.selected.pattern

    def matches(self, path: str) -> bool:
        artifact = _hlsync_artifact(path)
        return self.selected.matches(artifact.destination if artifact else path)

    def may_match_descendant(self, directory: str) -> bool:
        return self.selected.may_match_descendant(directory)


def _parse_modify_timestamp(
    value: str,
    path: str,
    *,
    source: str,
) -> tuple[int, int]:
    base, separator, fraction = value.partition(".")
    if len(base) != 14 or not base.isdigit() or (
        separator and (not fraction or not fraction.isdigit())
    ):
        raise TransportError(
            f"invalid {source} timestamp {value!r} for '{path}'"
        )
    try:
        timestamp = datetime.strptime(base, "%Y%m%d%H%M%S")
    except ValueError as error:
        raise TransportError(
            f"invalid {source} timestamp {value!r} for '{path}'"
        ) from error
    fraction_digits = min(len(fraction), 9)
    fractional_ns = int(fraction[:9].ljust(9, "0")) if fraction else 0
    precision_ns = 10 ** (9 - fraction_digits) if fraction else 1_000_000_000
    return timegm(timestamp.timetuple()) * 1_000_000_000 + fractional_ns, precision_ns


def _parse_mlsd_modify(value: str, path: str) -> tuple[int, int]:
    return _parse_modify_timestamp(value, path, source="MLSD modify")


def _parse_mdtm_response(response: str, path: str) -> tuple[int, int]:
    code, separator, value = response.partition(" ")
    if code != "213" or not separator or not value.strip():
        raise TransportError(
            f"invalid MDTM response for '{path}': {response}"
        )
    return _parse_modify_timestamp(value.strip(), path, source="MDTM")


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
        traverse_excluded: bool = False,
    ) -> TreeSnapshot: ...

    def list_directory(
        self,
        relative_directory: PurePosixPath,
        rules: RuleSet,
    ) -> TreeSnapshot: ...

    def make_directory(self, relative_path: str) -> None: ...

    def recover_artifacts(self, selector: FileSelection) -> tuple[str, ...]: ...

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
    configuration: ProfileConfiguration
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
                    f"could not open explicit FTPS profile at "
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
        traverse_excluded: bool = False,
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
                    traverse_excluded
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
        except ftplib.error_perm as error:
            display_path = remote_directory or "."
            raise PathOperationError(
                f"could not list remote directory '{display_path}': {error}"
            ) from error
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

    def recover_artifacts(self, selector: FileSelection) -> tuple[str, ...]:
        snapshot = self.snapshot(
            RuleSet(),
            _ArtifactRecoverySelection(selector),
            include_excluded=True,
        )
        entries = {entry.path: entry for entry in snapshot.entries}
        artifacts = tuple(
            artifact
            for path in sorted(entries)
            for artifact in (_hlsync_artifact(path),)
            if artifact is not None
        )
        for artifact in artifacts:
            if entries[artifact.path].kind != "file":
                raise TransportError(
                    f"reserved HLSync artifact is not a file: '{artifact.path}'"
                )

        messages: list[str] = []
        for artifact in artifacts:
            if artifact.kind != "upload":
                continue
            self.delete_path(artifact.path, is_directory=False)
            messages.append(f"Removed abandoned upload '{artifact.path}'.")

        backups_by_destination: dict[str, list[_HLSyncArtifact]] = {}
        for artifact in artifacts:
            if artifact.kind == "backup":
                backups_by_destination.setdefault(
                    artifact.destination,
                    [],
                ).append(artifact)
        client = self._connected_client()
        for destination, backups in sorted(backups_by_destination.items()):
            if destination not in entries and len(backups) > 1:
                names = ", ".join(backup.path for backup in backups)
                raise TransportError(
                    f"multiple HLSync backups require manual recovery for "
                    f"'{destination}': {names}"
                )
            if destination in entries:
                for backup in backups:
                    self.delete_path(backup.path, is_directory=False)
                    messages.append(f"Removed old backup '{backup.path}'.")
                continue
            backup = backups[0]
            try:
                client.rename(backup.path, destination)
            except ftplib.error_perm as error:
                raise PathOperationError(
                    f"could not restore HLSync backup '{backup.path}' to "
                    f"'{destination}': {error}"
                ) from error
            except (OSError, ftplib.Error, ssl.SSLError) as error:
                raise TransportError(
                    f"could not restore HLSync backup '{backup.path}' to "
                    f"'{destination}': {error}"
                ) from error
            messages.append(
                f"Restored interrupted replacement '{destination}'."
            )
        return tuple(messages)

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
        temporary = str(remote.with_name(f".{remote.name}.hlsync-upload-{token}"))
        backup = str(remote.with_name(f".{remote.name}.hlsync-backup-{token}"))
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
            if len(response) < 3 or not response[:3].isdigit() or response[0] != "2":
                raise TransportError(
                    f"remote server did not accept modification time for "
                    f"'{path}': {response}"
                )
            verification = client.sendcmd(f"MDTM {temporary}")
            remote_modified_ns, remote_precision_ns = _parse_mdtm_response(
                verification,
                path,
            )
            expected_modified_ns = (
                modified_ns // 1_000_000_000 * 1_000_000_000
            )
            comparison_precision_ns = max(
                remote_precision_ns,
                1_000_000_000,
            )
            if (
                remote_modified_ns // comparison_precision_ns
                != expected_modified_ns // comparison_precision_ns
            ):
                raise TransportError(
                    f"remote modification time verification failed for "
                    f"'{path}': expected {timestamp}, got "
                    f"{verification.partition(' ')[2]}"
                )
            current_source = os.fstat(local_path.fileno())
            if (
                current_source.st_size != size
                or current_source.st_mtime_ns != modified_ns
            ):
                raise TransportError(
                    f"local source changed while staging remote file '{path}'"
                )
        except TransportError:
            discard(temporary)
            raise
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

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from hls.comparison import ComparisonEntry, ComparisonPlan
from hls.snapshot import TreeEntry, TreeSnapshot
from hls.transport import RemoteTransport


class TransferError(RuntimeError):
    """Raised when a transfer plan cannot be executed safely."""


@dataclass(frozen=True)
class TransferResult:
    plan: ComparisonPlan

    @property
    def changed_count(self) -> int:
        return sum(
            entry.action
            not in {"unchanged", "skip", "excluded"}
            for entry in self.plan.entries
        )


def _entry_map(snapshot: TreeSnapshot) -> dict[str, TreeEntry]:
    return {entry.path: entry for entry in snapshot.entries}


def _preflight(plan: ComparisonPlan, local_root: Path, local: TreeSnapshot) -> None:
    conflicts = [entry.path for entry in plan.entries if entry.action == "conflict"]
    if conflicts:
        raise TransferError(
            "transfer has unresolved conflict(s): " + ", ".join(conflicts)
        )
    local_entries = _entry_map(local)
    for entry in plan.entries:
        if entry.action not in {"upload", "replace-remote", "replace-local"}:
            continue
        expected = local_entries[entry.path]
        path = local_root / Path(*PurePosixPath(entry.path).parts)
        try:
            current = path.stat(follow_symlinks=False)
        except OSError as error:
            raise TransferError(
                f"could not validate local source '{path}': {error}"
            ) from error
        if not stat.S_ISREG(current.st_mode):
            raise TransferError(f"local source is no longer a file: {path}")
        if (
            current.st_size != expected.size
            or current.st_mtime_ns != expected.modified_ns
        ):
            raise TransferError(f"local source changed after snapshot: {path}")


def _remote_directories_to_create(
    plan: ComparisonPlan,
    remote: TreeSnapshot,
) -> tuple[str, ...]:
    existing = {
        entry.path for entry in remote.entries if entry.kind == "directory"
    }
    required = {
        entry.path
        for entry in plan.entries
        if entry.action == "create-remote"
    }
    for entry in plan.entries:
        if entry.action not in {"upload", "replace-remote"}:
            continue
        parent = PurePosixPath(entry.path).parent
        while parent.parts:
            if parent.as_posix() not in existing:
                required.add(parent.as_posix())
            parent = parent.parent
    return tuple(
        sorted(
            required,
            key=lambda path: (len(PurePosixPath(path).parts), path),
        )
    )


def _push_files(
    plan: ComparisonPlan,
    local_root: Path,
    local: TreeSnapshot,
    remote: TreeSnapshot,
    transport: RemoteTransport,
) -> None:
    local_entries = _entry_map(local)
    for directory in _remote_directories_to_create(plan, remote):
        transport.make_directory(directory)
    for entry in plan.entries:
        if entry.action not in {"upload", "replace-remote"}:
            continue
        metadata = local_entries[entry.path]
        if metadata.size is None or metadata.modified_ns is None:
            raise TransferError(f"local file metadata is incomplete: {entry.path}")
        path = local_root / Path(*PurePosixPath(entry.path).parts)
        try:
            with path.open("rb") as source:
                transport.upload_file(
                    source,
                    entry.path,
                    size=metadata.size,
                    modified_ns=metadata.modified_ns,
                    replace=entry.action == "replace-remote",
                )
        except OSError as error:
            raise TransferError(
                f"could not read local file '{path}': {error}"
            ) from error


def _replace_local_file(
    root: Path,
    comparison: ComparisonEntry,
    local_entry: TreeEntry,
    remote_entry: TreeEntry,
    transport: RemoteTransport,
) -> None:
    destination = root / Path(*PurePosixPath(comparison.path).parts)
    try:
        mode = stat.S_IMODE(destination.stat(follow_symlinks=False).st_mode)
    except OSError as error:
        raise TransferError(
            f"could not inspect local destination '{destination}': {error}"
        ) from error
    descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent,
        prefix=f".{destination.name}.hls-pull-",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            transport.download_file(comparison.path, target)
            target.flush()
            os.fsync(target.fileno())
        actual_size = temporary.stat().st_size
        if actual_size != remote_entry.size:
            raise TransferError(
                f"download size mismatch for '{comparison.path}': expected "
                f"{remote_entry.size}, got {actual_size}"
            )
        os.chmod(temporary, mode)
        if remote_entry.modified_ns is None:
            raise TransferError(
                f"remote file timestamp is missing: {comparison.path}"
            )
        os.utime(
            temporary,
            ns=(remote_entry.modified_ns, remote_entry.modified_ns),
        )
        current = destination.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_size != local_entry.size
            or current.st_mtime_ns != local_entry.modified_ns
        ):
            raise TransferError(
                f"local destination changed during download: {destination}"
            )
        temporary.replace(destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _pull_files(
    plan: ComparisonPlan,
    local_root: Path,
    local: TreeSnapshot,
    remote: TreeSnapshot,
    transport: RemoteTransport,
) -> None:
    local_entries = _entry_map(local)
    remote_entries = _entry_map(remote)
    for entry in plan.entries:
        if entry.action == "replace-local":
            _replace_local_file(
                local_root,
                entry,
                local_entries[entry.path],
                remote_entries[entry.path],
                transport,
            )


def _delete_remote(plan: ComparisonPlan, transport: RemoteTransport) -> None:
    deletions = [
        entry for entry in plan.entries if entry.action == "delete-remote"
    ]
    files = sorted(
        (entry for entry in deletions if entry.remote_kind != "directory"),
        key=lambda entry: entry.path,
    )
    directories = sorted(
        (entry for entry in deletions if entry.remote_kind == "directory"),
        key=lambda entry: (-len(PurePosixPath(entry.path).parts), entry.path),
    )
    for entry in (*files, *directories):
        transport.delete_path(
            entry.path,
            is_directory=entry.remote_kind == "directory",
        )


def execute_transfer(
    plan: ComparisonPlan,
    *,
    local_root: Path,
    local: TreeSnapshot,
    remote: TreeSnapshot,
    transport: RemoteTransport,
) -> TransferResult:
    _preflight(plan, local_root, local)
    if plan.direction == "push":
        _push_files(plan, local_root, local, remote, transport)
    else:
        _pull_files(plan, local_root, local, remote, transport)
    _delete_remote(plan, transport)
    return TransferResult(plan)

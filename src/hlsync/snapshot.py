from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from hlsync.rules import RuleSet
from hlsync.selection import FileSelection

EntryKind = Literal["directory", "file", "symlink"]


class SnapshotError(RuntimeError):
    """Raised when a deterministic tree snapshot cannot be produced."""


@dataclass(frozen=True)
class TreeEntry:
    path: str
    kind: EntryKind
    size: int | None = None
    modified_ns: int | None = None
    timestamp_precision_ns: int | None = None
    excluded: bool = False
    remote_excluded: bool = False

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SnapshotError(f"snapshot path must be relative: {self.path!r}")
        object.__setattr__(self, "path", path.as_posix())
        if not isinstance(self.excluded, bool):
            raise SnapshotError("snapshot exclusion state must be a boolean")
        if not isinstance(self.remote_excluded, bool):
            raise SnapshotError("remote exclusion state must be a boolean")
        metadata = (self.size, self.modified_ns, self.timestamp_precision_ns)
        if self.kind == "file":
            if any(value is None for value in metadata):
                raise SnapshotError(
                    f"file snapshot metadata is incomplete: {self.path!r}"
                )
            if self.size is not None and self.size < 0:
                raise SnapshotError(f"file size cannot be negative: {self.path!r}")
            if (
                self.timestamp_precision_ns is not None
                and self.timestamp_precision_ns <= 0
            ):
                raise SnapshotError(
                    f"timestamp precision must be positive: {self.path!r}"
                )
        elif any(value is not None for value in metadata):
            raise SnapshotError(
                f"{self.kind} snapshot entry cannot have file metadata: "
                f"{self.path!r}"
            )


@dataclass(frozen=True)
class TreeSnapshot:
    entries: tuple[TreeEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.entries, key=lambda entry: entry.path))
        if len({entry.path for entry in ordered}) != len(ordered):
            raise SnapshotError("snapshot contains duplicate paths")
        object.__setattr__(self, "entries", ordered)


def snapshot_local(
    root: Path,
    rules: RuleSet,
    selector: FileSelection | None = None,
    *,
    include_excluded: bool = False,
    traverse_excluded: bool = False,
    respect_remote_boundaries: bool = False,
) -> TreeSnapshot:
    if not root.is_dir():
        raise SnapshotError(f"local root is not an accessible directory: {root}")
    entries: list[TreeEntry] = []

    def walk(relative_directory: PurePosixPath) -> None:
        listing = list_local_directory(root, relative_directory, rules)
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
                selector is None or selector.may_match_descendant(relative_path)
            )
            exclusion_may_descend = (
                traverse_excluded
                or not excluded
                or rules.may_include_descendant(relative_path)
            )
            remote_may_descend = (
                not respect_remote_boundaries or not entry.remote_excluded
            )
            if (
                kind == "directory"
                and selection_may_descend
                and exclusion_may_descend
                and remote_may_descend
            ):
                walk(relative)

    walk(PurePosixPath())
    return TreeSnapshot(tuple(entries))


def list_local_directory(
    root: Path,
    relative_directory: PurePosixPath,
    rules: RuleSet,
) -> TreeSnapshot:
    """Inspect one directory and return all immediate children."""
    directory = root / relative_directory
    try:
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda entry: entry.name)
    except OSError as error:
        raise SnapshotError(
            f"could not read local directory '{directory}': {error}"
        ) from error

    entries: list[TreeEntry] = []
    for child in children:
        relative = relative_directory / child.name
        relative_path = relative.as_posix()
        try:
            if child.is_symlink():
                kind: EntryKind = "symlink"
            elif child.is_dir(follow_symlinks=False):
                kind = "directory"
            elif child.is_file(follow_symlinks=False):
                kind = "file"
            else:
                raise SnapshotError(
                    f"unsupported local entry type: {directory / child.name}"
                )
        except OSError as error:
            raise SnapshotError(
                f"could not inspect local path '{directory / child.name}': {error}"
            ) from error

        excluded = rules.excludes(relative_path, is_directory=kind == "directory")
        remote_excluded = rules.excludes(
            relative_path, target="remote", is_directory=kind == "directory"
        )
        if kind == "file":
            try:
                stat = child.stat(follow_symlinks=False)
            except OSError as error:
                raise SnapshotError(
                    f"could not read local file metadata '{directory / child.name}': "
                    f"{error}"
                ) from error
            entries.append(
                TreeEntry(
                    relative_path,
                    kind,
                    size=stat.st_size,
                    modified_ns=stat.st_mtime_ns,
                    timestamp_precision_ns=1,
                    excluded=excluded,
                    remote_excluded=remote_excluded,
                )
            )
        else:
            entries.append(
                TreeEntry(
                    relative_path,
                    kind,
                    excluded=excluded,
                    remote_excluded=remote_excluded,
                )
            )
    return TreeSnapshot(tuple(entries))

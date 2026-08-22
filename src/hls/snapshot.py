from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from hls.exclusions import ExclusionSpec

EntryKind = Literal["directory", "file", "symlink"]


class SnapshotError(RuntimeError):
    """Raised when a deterministic tree snapshot cannot be produced."""


@dataclass(frozen=True, order=True)
class TreeEntry:
    path: str
    kind: EntryKind

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SnapshotError(f"snapshot path must be relative: {self.path!r}")
        object.__setattr__(self, "path", path.as_posix())


@dataclass(frozen=True)
class TreeSnapshot:
    entries: tuple[TreeEntry, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.entries, key=lambda entry: entry.path))
        if len({entry.path for entry in ordered}) != len(ordered):
            raise SnapshotError("snapshot contains duplicate paths")
        object.__setattr__(self, "entries", ordered)


def snapshot_local(root: Path, exclusions: ExclusionSpec) -> TreeSnapshot:
    if not root.is_dir():
        raise SnapshotError(f"local root is not an accessible directory: {root}")
    entries: list[TreeEntry] = []

    def walk(directory: Path, relative_directory: PurePosixPath) -> None:
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda entry: entry.name)
        except OSError as error:
            raise SnapshotError(
                f"could not read local directory '{directory}': {error}"
            ) from error

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

            if exclusions.excludes(
                relative_path,
                is_directory=kind == "directory",
            ):
                continue
            entries.append(TreeEntry(relative_path, kind))
            if kind == "directory":
                walk(directory / child.name, relative)

    walk(root, PurePosixPath())
    return TreeSnapshot(tuple(entries))

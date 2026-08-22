from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from hls.exclusions import ExclusionSpec
from hls.selection import FileSelection

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

    def __post_init__(self) -> None:
        path = PurePosixPath(self.path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SnapshotError(f"snapshot path must be relative: {self.path!r}")
        object.__setattr__(self, "path", path.as_posix())
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
    exclusions: ExclusionSpec,
    selector: FileSelection | None = None,
) -> TreeSnapshot:
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

            excluded = exclusions.excludes(
                relative_path,
                is_directory=kind == "directory",
            )
            selected = not excluded and (
                selector is None or selector.matches(relative_path)
            )
            if selected and kind == "file":
                try:
                    stat = child.stat(follow_symlinks=False)
                except OSError as error:
                    raise SnapshotError(
                        f"could not read local file metadata "
                        f"'{directory / child.name}': {error}"
                    ) from error
                entries.append(
                    TreeEntry(
                        relative_path,
                        kind,
                        size=stat.st_size,
                        modified_ns=stat.st_mtime_ns,
                        timestamp_precision_ns=1,
                    )
                )
            elif selected:
                entries.append(TreeEntry(relative_path, kind))
            selection_may_descend = (
                selector is None or selector.may_match_descendant(relative_path)
            )
            exclusion_may_descend = (
                not excluded or exclusions.may_include_descendant(relative_path)
            )
            if kind == "directory" and selection_may_descend and exclusion_may_descend:
                walk(directory / child.name, relative)

    walk(root, PurePosixPath())
    return TreeSnapshot(tuple(entries))

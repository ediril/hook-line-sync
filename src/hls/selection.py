from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import cache
from pathlib import Path, PurePosixPath


class SelectionError(ValueError):
    """Raised when a file selector is unsafe or matches no files."""


@cache
def _matches_parts(pattern: tuple[str, ...], path: tuple[str, ...]) -> bool:
    if not pattern:
        return not path
    head, *tail = pattern
    if head == "**":
        return _matches_parts(tuple(tail), path) or (
            bool(path) and _matches_parts(pattern, path[1:])
        )
    return bool(path) and fnmatchcase(path[0], head) and _matches_parts(
        tuple(tail), path[1:]
    )


@cache
def _can_match_descendant(
    pattern: tuple[str, ...],
    directory: tuple[str, ...],
) -> bool:
    if not directory:
        return bool(pattern)
    if not pattern:
        return False
    head, *tail = pattern
    if head == "**":
        return _can_match_descendant(tuple(tail), directory) or (
            _can_match_descendant(pattern, directory[1:])
        )
    return fnmatchcase(directory[0], head) and _can_match_descendant(
        tuple(tail), directory[1:]
    )


@dataclass(frozen=True)
class FileSelector:
    pattern: str

    def __post_init__(self) -> None:
        path = PurePosixPath(self.pattern)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise SelectionError(
                "file selector must be a non-empty relative path without '..'"
            )
        if any(character in self.pattern for character in "?["):
            raise SelectionError("file selector supports only '*' and '**' wildcards")
        if any("**" in part and part != "**" for part in path.parts):
            raise SelectionError("'**' must occupy an entire path segment")
        object.__setattr__(self, "pattern", path.as_posix())

    @classmethod
    def from_argument(
        cls,
        value: str,
        *,
        project_root: Path,
        current_directory: Path,
    ) -> FileSelector:
        if not value:
            raise SelectionError("file selector cannot be empty")
        try:
            current_relative = current_directory.relative_to(project_root)
        except ValueError:
            base = PurePosixPath()
        else:
            base = PurePosixPath(*current_relative.parts)
        supplied = PurePosixPath(value)
        if supplied.is_absolute() or ".." in supplied.parts:
            raise SelectionError(
                "file selector must be relative to the project or current directory"
            )
        return cls((base / supplied).as_posix())

    def matches(self, project_relative_path: str) -> bool:
        path = PurePosixPath(project_relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise SelectionError("selected paths must remain inside the project")
        return _matches_parts(PurePosixPath(self.pattern).parts, path.parts)

    def may_match_descendant(self, project_relative_directory: str) -> bool:
        directory = PurePosixPath(project_relative_directory)
        if directory.is_absolute() or ".." in directory.parts:
            raise SelectionError("selected paths must remain inside the project")
        return _can_match_descendant(
            PurePosixPath(self.pattern).parts,
            directory.parts,
        )


@dataclass(frozen=True)
class FileSelectorSet:
    selectors: tuple[FileSelector, ...]

    def __post_init__(self) -> None:
        if not self.selectors:
            raise SelectionError("file selector set cannot be empty")
        unique = {selector.pattern: selector for selector in self.selectors}
        object.__setattr__(
            self,
            "selectors",
            tuple(unique[pattern] for pattern in sorted(unique)),
        )

    @property
    def pattern(self) -> str:
        return ", ".join(selector.pattern for selector in self.selectors)

    def matches(self, project_relative_path: str) -> bool:
        return any(
            selector.matches(project_relative_path) for selector in self.selectors
        )

    def may_match_descendant(self, project_relative_directory: str) -> bool:
        return any(
            selector.may_match_descendant(project_relative_directory)
            for selector in self.selectors
        )


FileSelection = FileSelector | FileSelectorSet

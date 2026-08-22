from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from hls.selection import FileSelector, SelectionError

RuleAction = Literal["include", "exclude"]


class RuleError(ValueError):
    """Raised when an HLS synchronization rule is unsafe or malformed."""


def _relative_base(project_root: Path, current_directory: Path) -> PurePosixPath:
    try:
        relative = current_directory.relative_to(project_root)
    except ValueError:
        return PurePosixPath()
    return PurePosixPath(*relative.parts)


def patterns_from_operands(
    values: tuple[str, ...],
    *,
    project_root: Path,
    current_directory: Path,
) -> tuple[str, ...]:
    """Translate CLI operands into project-rooted HLS patterns."""
    base = _relative_base(project_root, current_directory)
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise RuleError("rule patterns must be non-empty strings")
        pattern = value.strip()
        supplied = PurePosixPath(pattern)
        if supplied.is_absolute() or ".." in supplied.parts:
            raise RuleError(
                "rule patterns must be relative to the project or current directory"
            )
        rooted = base / supplied
        local_path = project_root.joinpath(*rooted.parts)
        is_directory = pattern.endswith("/") or (
            "*" not in pattern
            and local_path.is_dir()
            and not local_path.is_symlink()
        )
        if is_directory:
            rooted = rooted / "**"
        candidate = rooted.as_posix()
        try:
            candidate = FileSelector(candidate).pattern
        except SelectionError as error:
            raise RuleError(str(error)) from error
        normalized.append(candidate)
    return tuple(normalized)


@dataclass(frozen=True)
class SyncRule:
    id: int
    action: RuleAction
    pattern: str

    def __post_init__(self) -> None:
        if isinstance(self.id, bool) or not isinstance(self.id, int) or self.id < 1:
            raise RuleError("rule id must be a positive integer")
        if not isinstance(self.action, str) or self.action not in {
            "include",
            "exclude",
        }:
            raise RuleError("rule action must be 'include' or 'exclude'")
        if not isinstance(self.pattern, str):
            raise RuleError("rule pattern must be a string")
        try:
            normalized = FileSelector(self.pattern).pattern
        except SelectionError as error:
            raise RuleError(str(error)) from error
        object.__setattr__(self, "pattern", normalized)
        object.__setattr__(self, "_selector", FileSelector(normalized))

    def matches(self, project_relative_path: str) -> bool:
        return self._selector.matches(project_relative_path)

    def may_match_descendant(self, project_relative_directory: str) -> bool:
        return self._selector.may_match_descendant(project_relative_directory)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "action": self.action, "pattern": self.pattern}

    @classmethod
    def from_dict(cls, value: Any) -> SyncRule:
        if not isinstance(value, dict) or set(value) != {"id", "action", "pattern"}:
            raise RuleError("each rule must contain only id, action, and pattern")
        return cls(id=value["id"], action=value["action"], pattern=value["pattern"])


@dataclass(frozen=True)
class RuleEvaluation:
    path: str
    matches: tuple[SyncRule, ...]

    @property
    def winner(self) -> SyncRule | None:
        return self.matches[-1] if self.matches else None

    @property
    def excluded(self) -> bool:
        return self.winner is not None and self.winner.action == "exclude"


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[SyncRule, ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(rule, SyncRule) for rule in self.rules):
            raise RuleError("rules must contain structured synchronization rules")
        ids = tuple(rule.id for rule in self.rules)
        if len(set(ids)) != len(ids):
            raise RuleError("rule ids must be unique")
        if ids != tuple(sorted(ids)):
            raise RuleError("rules must be ordered by increasing id")

    def evaluate(self, project_relative_path: str) -> RuleEvaluation:
        path = PurePosixPath(project_relative_path)
        if path.is_absolute() or not path.parts or ".." in path.parts:
            raise RuleError("evaluated paths must be non-empty project-relative paths")
        candidate = path.as_posix()
        return RuleEvaluation(
            candidate,
            tuple(rule for rule in self.rules if rule.matches(candidate)),
        )

    def excludes(self, relative_path: str, *, is_directory: bool = False) -> bool:
        del is_directory
        return self.evaluate(relative_path).excluded

    def may_include_descendant(self, relative_directory: str) -> bool:
        return any(
            rule.action == "include"
            and rule.may_match_descendant(relative_directory)
            for rule in self.rules
        )

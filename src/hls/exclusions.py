from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from pathspec import GitIgnoreSpec


class ExclusionError(ValueError):
    """Raised when exclusion patterns are unsafe or malformed."""


def _validate_pattern(pattern: object) -> str:
    if not isinstance(pattern, str):
        raise ExclusionError("exclusion patterns must be strings")
    normalized = pattern.strip()
    if not normalized:
        raise ExclusionError("exclusion patterns cannot be empty")
    if normalized.startswith("!"):
        raise ExclusionError("exclusion patterns cannot re-include paths with '!'")
    if ".." in PurePosixPath(normalized).parts:
        raise ExclusionError("exclusion patterns cannot contain '..'")
    return normalized


@dataclass(frozen=True)
class ExclusionSpec:
    patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(sorted({_validate_pattern(item) for item in self.patterns}))
        object.__setattr__(self, "patterns", normalized)
        object.__setattr__(self, "_matcher", GitIgnoreSpec.from_lines(normalized))

    @classmethod
    def from_csv(cls, value: str | None) -> ExclusionSpec:
        if value is None:
            return cls()
        return cls(tuple(value.split(",")))

    def excludes(self, relative_path: str, *, is_directory: bool = False) -> bool:
        path = PurePosixPath(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ExclusionError("matched paths must be relative to the local root")
        candidate = path.as_posix()
        if is_directory and not candidate.endswith("/"):
            candidate += "/"
        return self._matcher.match_file(candidate)

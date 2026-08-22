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
    candidate = normalized[1:] if normalized.startswith("!") else normalized
    if not candidate:
        raise ExclusionError("inclusion patterns cannot be empty")
    if candidate.startswith("!"):
        raise ExclusionError("patterns cannot begin with more than one '!'")
    if ".." in PurePosixPath(candidate).parts:
        raise ExclusionError("exclusion patterns cannot contain '..'")
    return normalized


def rules_from_csv(value: str, *, include: bool) -> tuple[str, ...]:
    patterns = tuple(_validate_pattern(item) for item in value.split(","))
    if any(pattern.startswith("!") for pattern in patterns):
        raise ExclusionError("command patterns must not begin with '!'")
    if include:
        return tuple(f"!{pattern}" for pattern in patterns)
    return patterns


def _literal_prefix(pattern: str) -> tuple[str, bool]:
    candidate = pattern[1:].lstrip("/")
    if "\\" in candidate:
        return "", True
    wildcard_at = min(
        (candidate.find(character) for character in "*?[" if character in candidate),
        default=len(candidate),
    )
    return candidate[:wildcard_at].rstrip("/"), wildcard_at < len(candidate)


@dataclass(frozen=True)
class ExclusionSpec:
    patterns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(_validate_pattern(item) for item in self.patterns)
        object.__setattr__(self, "patterns", normalized)
        object.__setattr__(self, "_matcher", GitIgnoreSpec.from_lines(normalized))

    def excludes(self, relative_path: str, *, is_directory: bool = False) -> bool:
        path = PurePosixPath(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise ExclusionError("matched paths must be relative to the local root")
        candidate = path.as_posix()
        if is_directory and not candidate.endswith("/"):
            candidate += "/"
        return self._matcher.match_file(candidate)

    def may_include_descendant(self, relative_directory: str) -> bool:
        directory = PurePosixPath(relative_directory)
        if directory.is_absolute() or ".." in directory.parts:
            raise ExclusionError("matched paths must be relative to the local root")
        candidate = directory.as_posix().rstrip("/")
        for pattern in self.patterns:
            if not pattern.startswith("!"):
                continue
            prefix, has_wildcard = _literal_prefix(pattern)
            if not prefix:
                return True
            if prefix == candidate or prefix.startswith(f"{candidate}/"):
                return True
            if has_wildcard and candidate.startswith(f"{prefix}/"):
                return True
        return False

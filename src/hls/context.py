from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hls.config import ConfigurationError, validate_project_name
from hls.storage import write_json_atomic

CONTEXT_VERSION = 1


def canonical_directory(directory: str | Path) -> Path:
    candidate = Path(directory).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ConfigurationError(f"directory does not exist: {candidate}") from error
    if not resolved.is_dir():
        raise ConfigurationError(f"path is not a directory: {candidate}")
    if resolved.parent == resolved:
        raise ConfigurationError("a project context cannot be set at filesystem root")
    return resolved


@dataclass
class DirectoryContexts:
    bindings: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for directory, project_name in self.bindings.items():
            path = Path(directory)
            if not path.is_absolute() or os.path.normpath(directory) != directory:
                raise ConfigurationError(
                    f"context directory must be a normalized absolute path: {directory}"
                )
            if path.parent == path:
                raise ConfigurationError(
                    "a project context cannot target filesystem root"
                )
            validate_project_name(project_name)

    def bind(self, directory: Path, project_name: str) -> None:
        self.bindings[os.fspath(directory)] = validate_project_name(project_name)

    def resolve(self, directory: Path) -> tuple[str, Path] | None:
        for candidate in (directory, *directory.parents):
            project_name = self.bindings.get(os.fspath(candidate))
            if project_name is not None:
                return project_name, candidate
        return None

    def clear(self, directory: Path) -> None:
        key = os.fspath(directory)
        if key not in self.bindings:
            raise ConfigurationError(
                f"no project context is set for directory '{directory}'"
            )
        del self.bindings[key]

    def remove_project(self, project_name: str) -> bool:
        retained = {
            directory: name
            for directory, name in self.bindings.items()
            if name != project_name
        }
        changed = len(retained) != len(self.bindings)
        self.bindings = retained
        return changed

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CONTEXT_VERSION,
            "contexts": dict(sorted(self.bindings.items())),
        }

    @classmethod
    def from_dict(cls, value: Any) -> DirectoryContexts:
        if not isinstance(value, dict):
            raise ConfigurationError("context document must be an object")
        if value.get("version") != CONTEXT_VERSION:
            raise ConfigurationError(
                f"unsupported context version: {value.get('version')!r}"
            )
        if set(value) != {"version", "contexts"}:
            raise ConfigurationError("context document has unknown or missing fields")
        contexts = value["contexts"]
        if not isinstance(contexts, dict):
            raise ConfigurationError("contexts must be an object")
        if not all(
            isinstance(directory, str) and isinstance(project_name, str)
            for directory, project_name in contexts.items()
        ):
            raise ConfigurationError("context directories and projects must be strings")
        return cls(bindings=contexts)


class DirectoryContextStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".hls" / "contexts.json"

    def load(self) -> DirectoryContexts:
        if not self.path.exists():
            return DirectoryContexts()
        try:
            with self.path.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigurationError(
                f"could not read context file {self.path}: {error}"
            ) from error
        return DirectoryContexts.from_dict(document)

    def save(self, contexts: DirectoryContexts) -> None:
        try:
            write_json_atomic(self.path, contexts.to_dict())
        except OSError as error:
            raise ConfigurationError(
                f"could not write context file {self.path}: {error}"
            ) from error

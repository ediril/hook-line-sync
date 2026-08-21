from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

CONFIG_VERSION = 4
PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigurationError(ValueError):
    """Raised when configuration is invalid or cannot be decoded."""


def validate_project_name(name: str) -> str:
    if not PROJECT_NAME_PATTERN.fullmatch(name):
        raise ConfigurationError(
            "project name must start with a letter or digit and contain "
            "only letters, digits, '.', '_', or '-'"
        )
    return name


def credential_environment_names(project_name: str) -> tuple[str, str]:
    validate_project_name(project_name)
    prefix = re.sub(r"[^A-Za-z0-9]", "_", project_name).upper()
    return f"{prefix}_FTPS_USERNAME", f"{prefix}_FTPS_PASSWORD"


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _environment_name(value: Any, field_name: str) -> str:
    name = _required_string(value, field_name)
    if not ENVIRONMENT_NAME_PATTERN.fullmatch(name):
        raise ConfigurationError(
            f"{field_name} is not a valid environment-variable name"
        )
    return name


def _paths_overlap(first: Path | PurePosixPath, second: Path | PurePosixPath) -> bool:
    return first == second or first in second.parents or second in first.parents


def _normalize_remote_path(value: Any, field_name: str = "mapping remote path") -> str:
    remote_value = _required_string(value, field_name)
    remote_path = PurePosixPath(remote_value)
    if not remote_path.is_absolute():
        raise ConfigurationError(f"{field_name} must be absolute")
    if ".." in remote_path.parts:
        raise ConfigurationError(f"{field_name} cannot contain '..'")
    components = [part for part in remote_path.parts if part not in {"/", "//"}]
    return "/" + "/".join(components)


@dataclass(frozen=True)
class DirectoryMapping:
    local: str
    remote: str

    def __post_init__(self) -> None:
        local_value = _required_string(self.local, "mapping local path")
        local_path = Path(local_value)
        if not local_path.is_absolute():
            raise ConfigurationError("mapping local path must be absolute")
        if local_path.parent == local_path:
            raise ConfigurationError("mapping local path cannot be the filesystem root")
        if os.path.normpath(local_value) != local_value:
            raise ConfigurationError("mapping local path must be normalized")

        if _normalize_remote_path(self.remote) != self.remote:
            raise ConfigurationError("mapping remote path must be normalized")

    @classmethod
    def create(cls, local: str | Path, remote: str) -> DirectoryMapping:
        candidate = Path(local).expanduser()
        try:
            local_path = candidate.resolve(strict=True)
        except OSError as error:
            raise ConfigurationError(
                f"local mapping folder does not exist: {candidate}"
            ) from error
        if not local_path.is_dir():
            raise ConfigurationError(f"local mapping path is not a folder: {candidate}")

        return cls(
            local=os.fspath(local_path), remote=_normalize_remote_path(remote)
        )

    def to_dict(self) -> dict[str, str]:
        return {"local": self.local, "remote": self.remote}

    @classmethod
    def from_dict(cls, value: Any) -> DirectoryMapping:
        if not isinstance(value, dict):
            raise ConfigurationError("mapping must be an object")
        expected = {"local", "remote"}
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown mapping fields: {', '.join(sorted(unknown))}"
            )
        try:
            return cls(local=value["local"], remote=value["remote"])
        except KeyError as error:
            raise ConfigurationError(
                f"mapping is missing field: {error.args[0]}"
            ) from error


@dataclass(frozen=True)
class ProjectConfiguration:
    host: str
    remote_root: str
    port: int = 21
    username_env: str = "FTPS_USERNAME"
    password_env: str = "FTPS_PASSWORD"
    type: str = "ftps"
    mappings: tuple[DirectoryMapping, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", _required_string(self.host, "host"))
        object.__setattr__(
            self,
            "remote_root",
            _normalize_remote_path(self.remote_root, "project remote root"),
        )
        if self.type != "ftps":
            raise ConfigurationError("server type must be 'ftps'")
        if isinstance(self.port, bool) or not isinstance(self.port, int):
            raise ConfigurationError("port must be an integer")
        if not 1 <= self.port <= 65535:
            raise ConfigurationError("port must be between 1 and 65535")
        object.__setattr__(
            self,
            "username_env",
            _environment_name(self.username_env, "username_env"),
        )
        object.__setattr__(
            self,
            "password_env",
            _environment_name(self.password_env, "password_env"),
        )
        for index, mapping in enumerate(self.mappings):
            self._validate_within_remote_root(mapping)
            for existing in self.mappings[:index]:
                self._validate_no_overlap(mapping, existing)

    def _validate_within_remote_root(self, mapping: DirectoryMapping) -> None:
        remote = PurePosixPath(mapping.remote)
        root = PurePosixPath(self.remote_root)
        if remote != root and root not in remote.parents:
            raise ConfigurationError(
                f"remote path '{mapping.remote}' is outside project root "
                f"'{self.remote_root}'"
            )

    @staticmethod
    def _validate_no_overlap(
        mapping: DirectoryMapping, existing: DirectoryMapping
    ) -> None:
        if _paths_overlap(Path(mapping.local), Path(existing.local)):
            raise ConfigurationError(
                f"local path '{mapping.local}' overlaps existing mapping "
                f"'{existing.local}'"
            )
        if _paths_overlap(
            PurePosixPath(mapping.remote), PurePosixPath(existing.remote)
        ):
            raise ConfigurationError(
                f"remote path '{mapping.remote}' overlaps existing mapping "
                f"'{existing.remote}'"
            )

    def with_mapping(self, mapping: DirectoryMapping) -> ProjectConfiguration:
        self._validate_within_remote_root(mapping)
        for existing in self.mappings:
            self._validate_no_overlap(mapping, existing)
        return ProjectConfiguration(
            host=self.host,
            remote_root=self.remote_root,
            port=self.port,
            username_env=self.username_env,
            password_env=self.password_env,
            type=self.type,
            mappings=(*self.mappings, mapping),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "host": self.host,
            "remote_root": self.remote_root,
            "port": self.port,
            "username_env": self.username_env,
            "password_env": self.password_env,
            "mappings": [
                mapping.to_dict()
                for mapping in sorted(
                    self.mappings, key=lambda item: (item.local, item.remote)
                )
            ],
        }

    @classmethod
    def from_dict(cls, value: Any) -> ProjectConfiguration:
        if not isinstance(value, dict):
            raise ConfigurationError("project configuration must be an object")
        expected = {
            "type",
            "host",
            "remote_root",
            "port",
            "username_env",
            "password_env",
            "mappings",
        }
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown project configuration fields: {', '.join(sorted(unknown))}"
            )
        try:
            mappings_value = value["mappings"]
            if not isinstance(mappings_value, list):
                raise ConfigurationError("project mappings must be an array")
            return cls(
                type=value["type"],
                host=value["host"],
                remote_root=value["remote_root"],
                port=value["port"],
                username_env=value["username_env"],
                password_env=value["password_env"],
                mappings=tuple(
                    DirectoryMapping.from_dict(mapping)
                    for mapping in mappings_value
                ),
            )
        except KeyError as error:
            raise ConfigurationError(
                f"project configuration is missing field: {error.args[0]}"
            ) from error


@dataclass
class ApplicationConfiguration:
    projects: dict[str, ProjectConfiguration] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in self.projects:
            validate_project_name(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CONFIG_VERSION,
            "projects": {
                name: project.to_dict()
                for name, project in sorted(self.projects.items())
            },
        }

    @classmethod
    def from_dict(cls, value: Any) -> ApplicationConfiguration:
        if not isinstance(value, dict):
            raise ConfigurationError("configuration document must be an object")
        if value.get("version") != CONFIG_VERSION:
            raise ConfigurationError(
                f"unsupported configuration version: {value.get('version')!r}"
            )
        expected = {"version", "projects"}
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown configuration fields: {', '.join(sorted(unknown))}"
            )
        projects_value = value.get("projects")
        if not isinstance(projects_value, dict):
            raise ConfigurationError("projects must be an object")
        projects = {
            validate_project_name(name): ProjectConfiguration.from_dict(project)
            for name, project in projects_value.items()
        }
        return cls(projects=projects)


class ConfigurationStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".hls" / "configs.json"

    def load(self) -> ApplicationConfiguration:
        if not self.path.exists():
            return ApplicationConfiguration()
        try:
            with self.path.open(encoding="utf-8") as handle:
                document = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ConfigurationError(
                f"could not read configuration file {self.path}: {error}"
            ) from error
        return ApplicationConfiguration.from_dict(document)

    def save(self, configuration: ApplicationConfiguration) -> None:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = json.dumps(configuration.to_dict(), indent=2, sort_keys=True) + "\n"
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            text=True,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                os.chmod(temporary_path, 0o600)
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            temporary_path.replace(self.path)
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise

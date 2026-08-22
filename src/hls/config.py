from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from hls.rules import RuleAction, RuleError, RuleSet, SyncRule
from hls.storage import write_json_atomic

CONFIG_VERSION = 7
PROJECT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
DEFAULT_USERNAME_ENV = "PROD_FTPS_USERNAME"
DEFAULT_PASSWORD_ENV = "PROD_FTPS_PASSWORD"


class ConfigurationError(ValueError):
    """Raised when configuration is invalid or cannot be decoded."""


def validate_project_name(name: str) -> str:
    if not PROJECT_NAME_PATTERN.fullmatch(name):
        raise ConfigurationError(
            "project name must start with a letter or digit and contain "
            "only letters, digits, '.', '_', or '-'"
        )
    return name


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


def _normalize_remote_root(value: Any) -> str:
    remote_value = _required_string(value, "project remote root")
    remote_path = PurePosixPath(remote_value)
    if not remote_path.is_absolute():
        raise ConfigurationError("project remote root must be absolute")
    if ".." in remote_path.parts:
        raise ConfigurationError("project remote root cannot contain '..'")
    components = [part for part in remote_path.parts if part not in {"/", "//"}]
    return "/" + "/".join(components)


def canonical_local_root(directory: str | Path) -> str:
    candidate = Path(directory).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ConfigurationError(f"local root does not exist: {candidate}") from error
    if not resolved.is_dir():
        raise ConfigurationError(f"local root is not a directory: {candidate}")
    if resolved.parent == resolved:
        raise ConfigurationError("local root cannot be the filesystem root")
    return os.fspath(resolved)


def _validate_stored_local_root(value: Any) -> str | None:
    if value is None:
        return None
    local = _required_string(value, "project local root")
    path = Path(local)
    if not path.is_absolute():
        raise ConfigurationError("project local root must be absolute")
    if path.parent == path:
        raise ConfigurationError("project local root cannot be the filesystem root")
    if os.path.normpath(local) != local:
        raise ConfigurationError("project local root must be normalized")
    return local


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


@dataclass(frozen=True)
class ProjectConfiguration:
    host: str
    remote_root: str
    port: int = 21
    username_env: str = DEFAULT_USERNAME_ENV
    password_env: str = DEFAULT_PASSWORD_ENV
    type: str = "ftps"
    local_root: str | None = None
    rules: tuple[SyncRule, ...] = ()
    next_rule_id: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", _required_string(self.host, "host"))
        object.__setattr__(
            self,
            "remote_root",
            _normalize_remote_root(self.remote_root),
        )
        if self.type != "ftps":
            raise ConfigurationError("project protocol must be 'ftps'")
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
        object.__setattr__(
            self,
            "local_root",
            _validate_stored_local_root(self.local_root),
        )
        try:
            rule_set = RuleSet(self.rules)
        except RuleError as error:
            raise ConfigurationError(str(error)) from error
        object.__setattr__(self, "rules", rule_set.rules)
        if (
            isinstance(self.next_rule_id, bool)
            or not isinstance(self.next_rule_id, int)
            or self.next_rule_id < 1
        ):
            raise ConfigurationError("next_rule_id must be a positive integer")
        if self.rules and self.next_rule_id <= self.rules[-1].id:
            raise ConfigurationError("next_rule_id must be greater than every rule id")
        if self.local_root is None and self.rules:
            raise ConfigurationError("an unmapped project cannot have rules")

    def with_local_root(self, local_root: str) -> ProjectConfiguration:
        if self.local_root is not None:
            raise ConfigurationError(
                f"project is already mapped to local root '{self.local_root}'"
            )
        return ProjectConfiguration(
            host=self.host,
            remote_root=self.remote_root,
            port=self.port,
            username_env=self.username_env,
            password_env=self.password_env,
            type=self.type,
            local_root=local_root,
            rules=(),
            next_rule_id=1,
        )

    def with_rules(
        self,
        rules: tuple[SyncRule, ...],
        *,
        next_rule_id: int | None = None,
    ) -> ProjectConfiguration:
        if self.local_root is None:
            raise ConfigurationError("cannot change rules for an unmapped project")
        return ProjectConfiguration(
            host=self.host,
            remote_root=self.remote_root,
            port=self.port,
            username_env=self.username_env,
            password_env=self.password_env,
            type=self.type,
            local_root=self.local_root,
            rules=rules,
            next_rule_id=self.next_rule_id if next_rule_id is None else next_rule_id,
        )

    def remote_path_for(self, local_path: Path) -> str:
        if self.local_root is None:
            raise ConfigurationError("project has no local root mapping")
        try:
            relative = local_path.relative_to(Path(self.local_root))
        except ValueError as error:
            raise ConfigurationError(
                f"local path '{local_path}' is outside project root '{self.local_root}'"
            ) from error
        if not relative.parts:
            return self.remote_root
        return str(PurePosixPath(self.remote_root) / PurePosixPath(*relative.parts))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "host": self.host,
            "remote_root": self.remote_root,
            "port": self.port,
            "username_env": self.username_env,
            "password_env": self.password_env,
            "local_root": self.local_root,
            "rules": [rule.to_dict() for rule in self.rules],
            "next_rule_id": self.next_rule_id,
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
            "local_root",
            "rules",
            "next_rule_id",
        }
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown project configuration fields: {', '.join(sorted(unknown))}"
            )
        try:
            rules = value["rules"]
            if not isinstance(rules, list):
                raise ConfigurationError("project rules must be an array")
            try:
                decoded_rules = tuple(SyncRule.from_dict(rule) for rule in rules)
            except RuleError as error:
                raise ConfigurationError(str(error)) from error
            return cls(
                type=value["type"],
                host=value["host"],
                remote_root=value["remote_root"],
                port=value["port"],
                username_env=value["username_env"],
                password_env=value["password_env"],
                local_root=value["local_root"],
                rules=decoded_rules,
                next_rule_id=value["next_rule_id"],
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
        mapped = [
            (name, Path(project.local_root))
            for name, project in self.projects.items()
            if project.local_root is not None
        ]
        for index, (name, root) in enumerate(mapped):
            for other_name, other_root in mapped[:index]:
                if _paths_overlap(root, other_root):
                    raise ConfigurationError(
                        f"project '{name}' local root '{root}' overlaps project "
                        f"'{other_name}' root '{other_root}'"
                    )

    def map_project(self, project_name: str, local_root: str) -> None:
        project = self.projects[project_name]
        if project.local_root is not None:
            raise ConfigurationError(
                f"project '{project_name}' is already mapped to "
                f"'{project.local_root}'"
            )
        root = Path(local_root)
        for other_name, other in self.projects.items():
            if other.local_root is None:
                continue
            other_root = Path(other.local_root)
            if _paths_overlap(root, other_root):
                raise ConfigurationError(
                    f"local root '{root}' for project '{project_name}' overlaps "
                    f"project '{other_name}' root '{other_root}'"
                )
        self.projects[project_name] = project.with_local_root(local_root)

    def append_rules(
        self,
        project_name: str,
        action: RuleAction,
        patterns: tuple[str, ...],
    ) -> tuple[SyncRule, ...]:
        project = self.projects[project_name]
        ordered = list(project.rules)
        added: list[SyncRule] = []
        next_rule_id = project.next_rule_id
        unique_patterns: list[str] = []
        for pattern in patterns:
            unique_patterns = [item for item in unique_patterns if item != pattern]
            unique_patterns.append(pattern)
        for pattern in unique_patterns:
            ordered = [rule for rule in ordered if rule.pattern != pattern]
            rule = SyncRule(next_rule_id, action, pattern)
            ordered.append(rule)
            added.append(rule)
            next_rule_id += 1
        self.projects[project_name] = project.with_rules(
            tuple(ordered),
            next_rule_id=next_rule_id,
        )
        return tuple(added)

    def remove_rule(self, project_name: str, rule_id: int) -> SyncRule:
        project = self.projects[project_name]
        removed = next((rule for rule in project.rules if rule.id == rule_id), None)
        if removed is None:
            raise ConfigurationError(
                f"project '{project_name}' has no rule with id {rule_id}"
            )
        remaining = tuple(rule for rule in project.rules if rule.id != rule_id)
        self.projects[project_name] = project.with_rules(remaining)
        return removed

    def project_for_path(
        self, local_path: Path
    ) -> tuple[str, ProjectConfiguration] | None:
        for name, project in sorted(self.projects.items()):
            if project.local_root is None:
                continue
            root = Path(project.local_root)
            if local_path == root or root in local_path.parents:
                return name, project
        return None

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
        if set(value) != {"version", "projects"}:
            raise ConfigurationError("configuration has unknown or missing fields")
        projects_value = value["projects"]
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
        try:
            write_json_atomic(self.path, configuration.to_dict())
        except OSError as error:
            raise ConfigurationError(
                f"could not write configuration file {self.path}: {error}"
            ) from error

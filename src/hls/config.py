from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_VERSION = 1
CONFIG_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ENVIRONMENT_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigurationError(ValueError):
    """Raised when configuration is invalid or cannot be decoded."""


def validate_config_name(name: str) -> str:
    if not CONFIG_NAME_PATTERN.fullmatch(name):
        raise ConfigurationError(
            "configuration name must start with a letter or digit and contain "
            "only letters, digits, '.', '_', or '-'"
        )
    return name


def credential_environment_names(config_name: str) -> tuple[str, str]:
    validate_config_name(config_name)
    prefix = re.sub(r"[^A-Za-z0-9]", "_", config_name).upper()
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


@dataclass(frozen=True)
class ServerConfiguration:
    host: str
    port: int = 21
    username_env: str = "FTPS_USERNAME"
    password_env: str = "FTPS_PASSWORD"
    type: str = "ftps"

    def __post_init__(self) -> None:
        object.__setattr__(self, "host", _required_string(self.host, "host"))
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

    def to_dict(self) -> dict[str, str | int]:
        return {
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "username_env": self.username_env,
            "password_env": self.password_env,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ServerConfiguration:
        if not isinstance(value, dict):
            raise ConfigurationError("server configuration must be an object")
        expected = {"type", "host", "port", "username_env", "password_env"}
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown server configuration fields: {', '.join(sorted(unknown))}"
            )
        try:
            return cls(
                type=value["type"],
                host=value["host"],
                port=value["port"],
                username_env=value["username_env"],
                password_env=value["password_env"],
            )
        except KeyError as error:
            raise ConfigurationError(
                f"server configuration is missing field: {error.args[0]}"
            ) from error


@dataclass
class ApplicationConfiguration:
    servers: dict[str, ServerConfiguration] = field(default_factory=dict)
    default: str | None = None

    def __post_init__(self) -> None:
        for name in self.servers:
            validate_config_name(name)
        if self.default is not None and self.default not in self.servers:
            raise ConfigurationError(
                f"default configuration '{self.default}' does not exist"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CONFIG_VERSION,
            "default": self.default,
            "servers": {
                name: server.to_dict()
                for name, server in sorted(self.servers.items())
            },
        }

    @classmethod
    def from_dict(cls, value: Any) -> ApplicationConfiguration:
        if not isinstance(value, dict):
            raise ConfigurationError("configuration document must be an object")
        expected = {"version", "default", "servers"}
        unknown = set(value) - expected
        if unknown:
            raise ConfigurationError(
                f"unknown configuration fields: {', '.join(sorted(unknown))}"
            )
        if value.get("version") != CONFIG_VERSION:
            raise ConfigurationError(
                f"unsupported configuration version: {value.get('version')!r}"
            )
        servers_value = value.get("servers")
        if not isinstance(servers_value, dict):
            raise ConfigurationError("servers must be an object")
        servers = {
            validate_config_name(name): ServerConfiguration.from_dict(server)
            for name, server in servers_value.items()
        }
        default = value.get("default")
        if default is not None and not isinstance(default, str):
            raise ConfigurationError("default must be a string or null")
        return cls(servers=servers, default=default)


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

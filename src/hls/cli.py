from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from hls import __version__
from hls.config import (
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    DirectoryMapping,
    ProjectConfiguration,
    credential_environment_names,
    validate_project_name,
)
from hls.transport import ExplicitFTPSTransport, TransportError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hls",
        description="Transfer mapped files over explicit FTP over TLS.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="add an FTPS project")
    add_parser.add_argument("project_name")
    add_parser.add_argument("type", choices=("ftps",))
    add_parser.add_argument("--host", required=True)
    add_parser.add_argument("--remote-root", required=True)
    add_parser.add_argument("--port", type=int, default=21)
    add_parser.add_argument("--username-env")
    add_parser.add_argument("--password-env")

    connect_parser = subparsers.add_parser(
        "connect", help="verify a project's FTPS connection"
    )
    connect_parser.add_argument("project_name")

    map_parser = subparsers.add_parser("map", help="add a folder mapping")
    map_parser.add_argument("project_name")
    map_parser.add_argument("remote_folder")
    map_parser.add_argument("local_folder", nargs="?", default=".")

    remove_parser = subparsers.add_parser("remove", help="remove a project")
    remove_parser.add_argument("project_name")

    help_parser = subparsers.add_parser("help", help="show command help")
    help_parser.add_argument("topic", nargs="?")

    subparsers.add_parser("version", help="show the installed version")
    return parser


def _save_project(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    name = validate_project_name(arguments.project_name)
    configuration = store.load()
    if name in configuration.projects:
        raise ConfigurationError(f"project '{name}' already exists")
    default_username_env, default_password_env = credential_environment_names(name)
    project = ProjectConfiguration(
        type=arguments.type,
        host=arguments.host,
        remote_root=arguments.remote_root,
        port=arguments.port,
        username_env=arguments.username_env or default_username_env,
        password_env=arguments.password_env or default_password_env,
    )
    configuration.projects[name] = project
    store.save(configuration)
    return f"Added FTPS project '{name}'."


def _resolve_project(
    arguments: argparse.Namespace, store: ConfigurationStore
) -> tuple[ApplicationConfiguration, str, ProjectConfiguration]:
    name = validate_project_name(arguments.project_name)
    configuration = store.load()
    if name not in configuration.projects:
        raise ConfigurationError(f"project '{name}' does not exist")
    return configuration, name, configuration.projects[name]


def _connect(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    _, name, project = _resolve_project(arguments, store)
    with ExplicitFTPSTransport(project):
        pass
    return f"Connected securely to project '{name}'."


def _map(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    mapping = DirectoryMapping.create(
        local=Path(arguments.local_folder), remote=arguments.remote_folder
    )
    configuration.projects[name] = project.with_mapping(mapping)
    store.save(configuration)
    return f"Mapped '{mapping.local}' to '{name}:{mapping.remote}'."


def _remove(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, _ = _resolve_project(arguments, store)
    del configuration.projects[name]
    store.save(configuration)
    return f"Removed project '{name}'."


def _show_help(parser: argparse.ArgumentParser, topic: str | None) -> str:
    if topic is None:
        return parser.format_help().rstrip()
    subparser = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    if topic not in subparser.choices:
        raise ConfigurationError(f"unknown help topic '{topic}'")
    return subparser.choices[topic].format_help().rstrip()


def run(
    argv: Sequence[str] | None = None,
    *,
    store: ConfigurationStore | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    configuration_store = store or ConfigurationStore()
    try:
        if arguments.command == "add":
            message = _save_project(arguments, configuration_store)
        elif arguments.command == "connect":
            message = _connect(arguments, configuration_store)
        elif arguments.command == "map":
            message = _map(arguments, configuration_store)
        elif arguments.command == "remove":
            message = _remove(arguments, configuration_store)
        elif arguments.command == "help":
            message = _show_help(parser, arguments.topic)
        elif arguments.command == "version":
            message = __version__
        else:
            parser.error(f"unknown command: {arguments.command}")
            return 2
    except (ConfigurationError, TransportError) as error:
        print(f"hls: error: {error}", file=stderr)
        return 1
    print(message, file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

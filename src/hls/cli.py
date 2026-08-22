from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from hls import __version__
from hls.config import (
    DEFAULT_PASSWORD_ENV,
    DEFAULT_USERNAME_ENV,
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    DirectoryMapping,
    ProjectConfiguration,
    validate_project_name,
)
from hls.context import DirectoryContextStore, canonical_directory
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
    add_parser.add_argument("--host", required=True)
    add_parser.add_argument("--remote-root", required=True)
    add_parser.add_argument("--protocol", choices=("ftps",), default="ftps")
    add_parser.add_argument("--port", type=int, default=21)
    add_parser.add_argument("--username-env")
    add_parser.add_argument("--password-env")

    connect_parser = subparsers.add_parser(
        "connect", help="verify a project's FTPS connection"
    )
    connect_parser.add_argument("project_name", nargs="?")

    map_parser = subparsers.add_parser("map", help="add a folder mapping")
    map_parser.add_argument("local_folder")
    map_parser.add_argument("remote_folder", nargs="?")
    map_parser.add_argument("--project", dest="project_name")

    remove_parser = subparsers.add_parser("remove", help="remove a project")
    remove_parser.add_argument("project_name")

    use_parser = subparsers.add_parser(
        "use", help="manage the project context for this directory"
    )
    use_parser.add_argument("project_name", nargs="?")
    use_parser.add_argument("--clear", action="store_true")

    list_parser = subparsers.add_parser(
        "list", aliases=("ls",), help="list configured projects"
    )
    list_parser.add_argument(
        "target", nargs="?", choices=("projects",), default="projects"
    )

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
    project = ProjectConfiguration(
        type=arguments.protocol,
        host=arguments.host,
        remote_root=arguments.remote_root,
        port=arguments.port,
        username_env=(
            arguments.username_env
            if arguments.username_env is not None
            else DEFAULT_USERNAME_ENV
        ),
        password_env=(
            arguments.password_env
            if arguments.password_env is not None
            else DEFAULT_PASSWORD_ENV
        ),
    )
    configuration.projects[name] = project
    store.save(configuration)
    return f"Added FTPS project '{name}'."


def _resolve_project(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> tuple[ApplicationConfiguration, str, ProjectConfiguration]:
    supplied_name = getattr(arguments, "project_name", None)
    if supplied_name is None:
        resolved = context_store.load().resolve(canonical_directory(Path.cwd()))
        if resolved is None:
            raise ConfigurationError(
                "no project was supplied and no directory context is active"
            )
        supplied_name, _ = resolved
    name = validate_project_name(supplied_name)
    configuration = store.load()
    if name not in configuration.projects:
        raise ConfigurationError(f"project '{name}' does not exist")
    return configuration, name, configuration.projects[name]


def _connect(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> str:
    _, name, project = _resolve_project(arguments, store, context_store)
    with ExplicitFTPSTransport(project):
        pass
    return f"Connected securely to project '{name}'."


def _map(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> str:
    configuration, name, project = _resolve_project(
        arguments, store, context_store
    )
    mapping = DirectoryMapping.create(
        local=Path(arguments.local_folder), remote=arguments.remote_folder
    )
    configuration.projects[name] = project.with_mapping(mapping)
    store.save(configuration)
    return f"Mapped '{mapping.local}' to '{name}:{project.remote_path(mapping)}'."


def _remove(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> str:
    configuration, name, _ = _resolve_project(arguments, store, context_store)
    contexts = context_store.load()
    if contexts.remove_project(name):
        context_store.save(contexts)
    del configuration.projects[name]
    store.save(configuration)
    return f"Removed project '{name}'."


def _use(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> str:
    if arguments.clear and arguments.project_name is not None:
        raise ConfigurationError("use accepts a project name or --clear, not both")
    directory = canonical_directory(Path.cwd())
    contexts = context_store.load()
    if arguments.clear:
        contexts.clear(directory)
        context_store.save(contexts)
        return f"Cleared project context for '{directory}'."
    if arguments.project_name is not None:
        name = validate_project_name(arguments.project_name)
        if name not in store.load().projects:
            raise ConfigurationError(f"project '{name}' does not exist")
        contexts.bind(directory, name)
        context_store.save(contexts)
        return f"Using project '{name}' in '{directory}'."
    resolved = contexts.resolve(directory)
    if resolved is None:
        raise ConfigurationError(f"no project context is active for '{directory}'")
    name, source = resolved
    if name not in store.load().projects:
        raise ConfigurationError(
            f"directory context at '{source}' references missing project '{name}'"
        )
    return f"Using project '{name}' from '{source}'."


def _list_projects(
    store: ConfigurationStore,
    context_store: DirectoryContextStore,
) -> str:
    configuration = store.load()
    if not configuration.projects:
        return "No projects configured."

    resolved = context_store.load().resolve(Path.cwd().resolve(strict=True))
    active_name = resolved[0] if resolved is not None else None
    lines: list[str] = []
    for name, project in sorted(configuration.projects.items()):
        marker = "*" if name == active_name else "-"
        lines.append(f"{marker} {name}")
        lines.append(f"  FTPS: {project.host}:{project.port}")
        lines.append(f"  Remote root: {project.remote_root}")
        if project.mappings:
            lines.append("  Mappings:")
            for mapping in sorted(
                project.mappings, key=lambda item: (item.local, item.remote)
            ):
                lines.append(
                    f"    {mapping.local} -> {project.remote_path(mapping)}"
                )
        else:
            lines.append("  Mappings: none")

    if resolved is not None:
        name, source = resolved
        lines.append("")
        if name in configuration.projects:
            lines.append(f"* active project from '{source}'")
        else:
            lines.append(
                f"! context at '{source}' references missing project '{name}'"
            )
    return "\n".join(lines)


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
    context_store: DirectoryContextStore | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    configuration_store = store or ConfigurationStore()
    directory_context_store = context_store or DirectoryContextStore()
    try:
        if arguments.command == "add":
            message = _save_project(arguments, configuration_store)
        elif arguments.command == "connect":
            message = _connect(
                arguments, configuration_store, directory_context_store
            )
        elif arguments.command == "map":
            message = _map(arguments, configuration_store, directory_context_store)
        elif arguments.command == "remove":
            message = _remove(
                arguments, configuration_store, directory_context_store
            )
        elif arguments.command == "use":
            message = _use(arguments, configuration_store, directory_context_store)
        elif arguments.command in {"list", "ls"}:
            message = _list_projects(
                configuration_store, directory_context_store
            )
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

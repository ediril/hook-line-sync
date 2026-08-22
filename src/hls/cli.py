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
    ProjectConfiguration,
    canonical_local_root,
    validate_project_name,
)
from hls.exclusions import ExclusionError, ExclusionSpec
from hls.snapshot import SnapshotError, TreeSnapshot, snapshot_local
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

    map_parser = subparsers.add_parser(
        "map", help="map the current directory to a project"
    )
    map_parser.add_argument("project_name")
    map_parser.add_argument(
        "--exclude",
        help="comma-separated gitignore-style patterns relative to the local root",
    )

    remove_parser = subparsers.add_parser("remove", help="remove a project")
    remove_parser.add_argument("project_name")

    list_parser = subparsers.add_parser(
        "list", aliases=("ls",), help="list configured projects"
    )
    list_parser.add_argument(
        "target",
        nargs="?",
        choices=("projects", "local", "remote"),
        default="projects",
    )
    list_parser.add_argument("project_name", nargs="?")

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
    arguments: argparse.Namespace, store: ConfigurationStore
) -> tuple[ApplicationConfiguration, str, ProjectConfiguration]:
    configuration = store.load()
    supplied_name = getattr(arguments, "project_name", None)
    if supplied_name is None:
        active = configuration.project_for_path(Path.cwd().resolve(strict=True))
        if active is None:
            raise ConfigurationError(
                "current directory is not inside a mapped project"
            )
        name, project = active
        return configuration, name, project
    name = validate_project_name(supplied_name)
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
    local_root = canonical_local_root(Path.cwd())
    exclusions = ExclusionSpec.from_csv(arguments.exclude).patterns
    configuration.map_project(name, local_root, exclusions)
    store.save(configuration)
    message = f"Mapped '{local_root}' to '{name}:{project.remote_root}'."
    if exclusions:
        message += f" Excluding: {', '.join(exclusions)}."
    return message


def _remove(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, _ = _resolve_project(arguments, store)
    del configuration.projects[name]
    store.save(configuration)
    return f"Removed project '{name}'."


def _list_projects(store: ConfigurationStore) -> str:
    configuration = store.load()
    if not configuration.projects:
        return "No projects configured."

    active = configuration.project_for_path(Path.cwd().resolve(strict=True))
    active_name = active[0] if active is not None else None
    lines: list[str] = []
    for name, project in sorted(configuration.projects.items()):
        marker = "*" if name == active_name else "-"
        lines.append(f"{marker} {name}")
        lines.append(f"  FTPS: {project.host}:{project.port}")
        lines.append(f"  Remote root: {project.remote_root}")
        lines.append(f"  Local root: {project.local_root or 'not mapped'}")
        if project.exclusions:
            lines.append(f"  Excludes: {', '.join(project.exclusions)}")
        else:
            lines.append("  Excludes: none")
    return "\n".join(lines)


def _require_local_root(name: str, project: ProjectConfiguration) -> Path:
    if project.local_root is None:
        raise ConfigurationError(f"project '{name}' has not been mapped")
    return Path(project.local_root)


def _format_snapshot(source: str, name: str, snapshot: TreeSnapshot) -> str:
    if not snapshot.entries:
        return f"{source} tree for project '{name}' is empty."
    lines = [f"{source} tree for project '{name}':"]
    for entry in snapshot.entries:
        path = f"{entry.path}/" if entry.kind == "directory" else entry.path
        lines.append(f"  {entry.kind:<9} {path}")
    return "\n".join(lines)


def _list_local(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    snapshot = snapshot_local(root, ExclusionSpec(project.exclusions))
    return _format_snapshot("Local", name, snapshot)


def _list_remote(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    _, name, project = _resolve_project(arguments, store)
    _require_local_root(name, project)
    with ExplicitFTPSTransport(project) as transport:
        snapshot = transport.snapshot(ExclusionSpec(project.exclusions))
    return _format_snapshot("Remote", name, snapshot)


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
        elif arguments.command in {"list", "ls"}:
            if arguments.target == "projects":
                if arguments.project_name is not None:
                    raise ConfigurationError(
                        "list projects does not accept a project name"
                    )
                message = _list_projects(configuration_store)
            elif arguments.target == "local":
                message = _list_local(arguments, configuration_store)
            else:
                message = _list_remote(arguments, configuration_store)
        elif arguments.command == "help":
            message = _show_help(parser, arguments.topic)
        elif arguments.command == "version":
            message = __version__
        else:
            parser.error(f"unknown command: {arguments.command}")
            return 2
    except (
        ConfigurationError,
        ExclusionError,
        SnapshotError,
        TransportError,
    ) as error:
        print(f"hls: error: {error}", file=stderr)
        return 1
    print(message, file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

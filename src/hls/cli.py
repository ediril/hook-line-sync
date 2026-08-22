from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from hls import __version__
from hls.comparison import ComparisonEntry, ComparisonPlan, build_comparison
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
from hls.exclusions import ExclusionError, ExclusionSpec, rules_from_patterns
from hls.pattern_operands import (
    PatternOperandError,
    add_pattern_operands,
    normalize_pattern_operands,
)
from hls.selection import FileSelection, FileSelector, FileSelectorSet, SelectionError
from hls.snapshot import SnapshotError, TreeSnapshot, snapshot_local
from hls.transfer import TransferError, TransferResult, execute_transfer
from hls.transport import ExplicitFTPSTransport, TransportError

CANONICAL_COMMANDS = (
    "add",
    "connect",
    "map",
    "remove",
    "list",
    "lsl",
    "lsr",
    "compare",
    "push",
    "pull",
    "exclude",
    "include",
    "help",
    "version",
)
COMMAND_ALIASES = {"ls": "list", "cmp": "compare"}


def _resolve_command_name(value: str) -> str:
    if value in CANONICAL_COMMANDS:
        return value
    if value in COMMAND_ALIASES:
        return COMMAND_ALIASES[value]
    matches = tuple(
        command for command in CANONICAL_COMMANDS if command.startswith(value)
    )
    if not matches:
        raise ConfigurationError(f"unknown command '{value}'")
    if len(matches) > 1:
        raise ConfigurationError(
            f"ambiguous command '{value}': {', '.join(matches)}"
        )
    return matches[0]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hls",
        description=(
            "Transfer mapped files over explicit FTP over TLS. Commands may be "
            "shortened to any unique prefix."
        ),
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

    for command, help_text in (
        ("exclude", "permanently exclude paths from synchronization"),
        ("include", "permanently re-include paths in synchronization"),
    ):
        rules_parser = subparsers.add_parser(command, help=help_text)
        add_pattern_operands(
            rules_parser,
            required=True,
            help_text=(
                "gitignore-style patterns or comma-separated pattern groups "
                "relative to the local root"
            ),
        )
        rules_parser.add_argument(
            "--project",
            dest="project_name",
            help="project name; inferred from the current directory when omitted",
        )

    remove_parser = subparsers.add_parser("remove", help="remove a project")
    remove_parser.add_argument("project_name")

    list_parser = subparsers.add_parser("list", help="list configured projects")
    list_parser.add_argument(
        "target",
        nargs="?",
        choices=("projects", "local", "remote"),
        default="projects",
    )
    list_parser.add_argument("project_name", nargs="?")

    local_list_parser = subparsers.add_parser(
        "lsl", help="list the local tree for a mapped project"
    )
    local_list_parser.add_argument("project_name", nargs="?")

    remote_list_parser = subparsers.add_parser(
        "lsr", help="list the remote tree for a mapped project"
    )
    remote_list_parser.add_argument("project_name", nargs="?")

    compare_parser = subparsers.add_parser(
        "compare",
        help="preview file changes without modifying anything",
        description=(
            "Preview file changes without modifying local or remote files. "
            "Shows the local perspective by default; use --pull for the remote "
            "perspective."
        ),
    )
    add_pattern_operands(
        compare_parser,
        required=False,
        help_text=(
            "relative file paths or wildcard patterns; defaults to the whole project"
        ),
    )
    compare_parser.add_argument(
        "--project",
        dest="project_name",
        help="project name; inferred from the current directory when omitted",
    )
    compare_parser.add_argument(
        "--pull",
        action="store_true",
        help="show changes from the remote perspective",
    )
    compare_parser.add_argument(
        "-p",
        "--prune-remote",
        action="store_true",
        help="project deletion of remote-only paths",
    )
    compare_parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="color status lines; defaults to auto detection",
    )

    transfer_help = {
        "push": "upload local changes to the remote project",
        "pull": "replace changed local files from the remote project",
    }
    transfer_description = {
        "push": (
            "Upload new and changed local files. Remote-only files are reported "
            "and left untouched unless --prune-remote is supplied."
        ),
        "pull": (
            "Replace changed existing local files from the remote project. "
            "Missing local files are not restored."
        ),
    }
    for command in ("push", "pull"):
        transfer_parser = subparsers.add_parser(
            command,
            help=transfer_help[command],
            description=transfer_description[command],
        )
        add_pattern_operands(
            transfer_parser,
            required=False,
            help_text=(
                "relative file paths or wildcard patterns; defaults to the whole "
                "project"
            ),
        )
        transfer_parser.add_argument(
            "--project",
            dest="project_name",
            help="project name; inferred from the current directory when omitted",
        )
        transfer_parser.add_argument(
            "-p",
            "--prune-remote",
            action="store_true",
            help="delete selected remote-only paths",
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
    return f"Verified secure connectivity to project '{name}'."


def _map(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    local_root = canonical_local_root(Path.cwd())
    configuration.map_project(name, local_root)
    store.save(configuration)
    return f"Mapped '{local_root}' to '{name}:{project.remote_root}'."


def _change_exclusions(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    *,
    include: bool,
) -> str:
    configuration, name, _ = _resolve_project(arguments, store)
    rules = rules_from_patterns(
        normalize_pattern_operands(arguments),
        include=include,
    )
    configuration.append_exclusion_rules(name, rules)
    store.save(configuration)
    action = "Included" if include else "Excluded"
    displayed_rules = (rule[1:] if include else rule for rule in rules)
    return "\n".join(
        (f"{action} for project '{name}':", *(f"  {rule}" for rule in displayed_rules))
    )


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
            rules = ", ".join(
                f"include {rule[1:]}" if rule.startswith("!") else f"exclude {rule}"
                for rule in project.exclusions
            )
            lines.append(f"  Rules: {rules}")
        else:
            lines.append("  Rules: none")
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


def _comparison_kind(entry: ComparisonEntry) -> str:
    if (
        entry.local_kind is not None
        and entry.remote_kind is not None
        and entry.local_kind != entry.remote_kind
    ):
        return f"{entry.local_kind}->{entry.remote_kind}"
    return entry.local_kind or entry.remote_kind or "unknown"


def _comparison_marker(entry: ComparisonEntry, direction: str) -> str:
    if entry.action == "excluded":
        return "·"
    if entry.action == "conflict":
        return "!"
    if entry.state == "changed":
        return "~"
    if direction == "push":
        return "+" if entry.state == "local-only" else "-"
    return "+" if entry.state == "remote-only" else "-"


def _use_color(mode: str, output: TextIO) -> bool:
    if mode == "always":
        return True
    if mode == "never" or "NO_COLOR" in os.environ:
        return False
    is_terminal = getattr(output, "isatty", None)
    return bool(is_terminal and is_terminal())


def _format_comparison(
    name: str,
    plan: ComparisonPlan,
    *,
    color: bool,
) -> str:
    perspective = "Local -> Remote" if plan.direction == "push" else "Remote -> Local"
    if not plan.differences:
        return f"{perspective} for project '{name}': no differences."
    lines = [f"{perspective} for project '{name}':"]
    colors = {
        "+": "\033[32m",
        "~": "\033[33m",
        "-": "\033[31m",
        "!": "\033[35m",
        "·": "\033[90m",
    }
    for entry in plan.differences:
        marker = _comparison_marker(entry, plan.direction)
        line = f"{marker}  {entry.path}"
        lines.append(f"{colors[marker]}{line}\033[0m" if color else line)
    return "\n".join(lines)


def _file_selection(arguments: argparse.Namespace, root: Path) -> FileSelection | None:
    selectors = tuple(
        FileSelector.from_argument(
            value,
            project_root=root,
            current_directory=Path.cwd().resolve(strict=True),
        )
        for value in normalize_pattern_operands(arguments)
    )
    if not selectors:
        return None
    if len(selectors) == 1:
        return selectors[0]
    return FileSelectorSet(selectors)


def _build_plan(
    arguments: argparse.Namespace,
    project: ProjectConfiguration,
    root: Path,
    transport: ExplicitFTPSTransport,
    *,
    direction: str,
    progress: TextIO,
    include_excluded: bool = False,
) -> tuple[TreeSnapshot, TreeSnapshot, ComparisonPlan]:
    exclusions = ExclusionSpec(project.exclusions)
    selector = _file_selection(arguments, root)
    print("Scanning local files...", file=progress, flush=True)
    local = snapshot_local(
        root,
        exclusions,
        selector,
        include_excluded=include_excluded,
    )
    print("Reading remote files over FTPS...", file=progress, flush=True)
    remote = transport.snapshot(
        exclusions,
        selector,
        include_excluded=include_excluded,
    )
    print(f"Building {direction} plan...", file=progress, flush=True)
    plan = build_comparison(
        local,
        remote,
        direction=direction,
        prune_remote=arguments.prune_remote,
        selector=selector,
    )
    return local, remote, plan


def _compare(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    progress: TextIO,
    output: TextIO,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    print(f"Comparing project '{name}'...", file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    with ExplicitFTPSTransport(project) as transport:
        _, _, plan = _build_plan(
            arguments,
            project,
            root,
            transport,
            direction="pull" if arguments.pull else "push",
            progress=progress,
            include_excluded=True,
        )
    return _format_comparison(
        name,
        plan,
        color=_use_color(arguments.color, output),
    )


def _format_transfer(name: str, result: TransferResult) -> str:
    direction = result.plan.direction.capitalize()
    lines = [
        f"{direction} completed for project '{name}': "
        f"{result.changed_count} change(s)."
    ]
    for entry in result.plan.differences:
        lines.append(
            f"  {entry.action:<14} {entry.state:<16} "
            f"{_comparison_kind(entry):<20} {entry.path}"
        )
    return "\n".join(lines)


def _transfer(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    progress: TextIO,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    print(
        f"Preparing {arguments.command} for project '{name}'...",
        file=progress,
        flush=True,
    )
    print("Connecting securely over FTPS...", file=progress, flush=True)
    with ExplicitFTPSTransport(project) as transport:
        local, remote, plan = _build_plan(
            arguments,
            project,
            root,
            transport,
            direction=arguments.command,
            progress=progress,
        )
        print(f"Executing {arguments.command} plan...", file=progress, flush=True)
        result = execute_transfer(
            plan,
            local_root=root,
            local=local,
            remote=remote,
            transport=transport,
        )
    return _format_transfer(name, result)


def _show_help(parser: argparse.ArgumentParser, topic: str | None) -> str:
    if topic is None:
        return parser.format_help().rstrip()
    subparser = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    resolved = _resolve_command_name(topic)
    return subparser.choices[resolved].format_help().rstrip()


def run(
    argv: Sequence[str] | None = None,
    *,
    store: ConfigurationStore | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    parser = build_parser()
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if raw_arguments and not raw_arguments[0].startswith("-"):
        try:
            raw_arguments[0] = _resolve_command_name(raw_arguments[0])
        except ConfigurationError as error:
            parser.error(str(error))
    arguments = parser.parse_args(raw_arguments)
    configuration_store = store or ConfigurationStore()
    try:
        if arguments.command == "add":
            message = _save_project(arguments, configuration_store)
        elif arguments.command == "connect":
            message = _connect(arguments, configuration_store)
        elif arguments.command == "map":
            message = _map(arguments, configuration_store)
        elif arguments.command == "exclude":
            message = _change_exclusions(
                arguments, configuration_store, include=False
            )
        elif arguments.command == "include":
            message = _change_exclusions(arguments, configuration_store, include=True)
        elif arguments.command == "remove":
            message = _remove(arguments, configuration_store)
        elif arguments.command == "list":
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
        elif arguments.command == "lsl":
            message = _list_local(arguments, configuration_store)
        elif arguments.command == "lsr":
            message = _list_remote(arguments, configuration_store)
        elif arguments.command == "compare":
            message = _compare(arguments, configuration_store, stderr, stdout)
        elif arguments.command in {"push", "pull"}:
            message = _transfer(arguments, configuration_store, stderr)
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
        PatternOperandError,
        SelectionError,
        SnapshotError,
        TransportError,
        TransferError,
    ) as error:
        print(f"hls: error: {error}", file=stderr)
        return 1
    print(message, file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

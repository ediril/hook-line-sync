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
from hls.pattern_operands import (
    PatternOperandError,
    add_pattern_operands,
    normalize_pattern_operands,
)
from hls.rules import RuleError, RuleSet, SyncRule, patterns_from_operands
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
    "diff",
    "push",
    "pull",
    "exclude",
    "include",
    "tracked",
    "rules",
    "help",
    "version",
)
COMMAND_ALIASES = {"ls": "list"}


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

    add_parser = subparsers.add_parser(
        "add", help="add an FTPS project and offer to map the current directory"
    )
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
        "map", help="map or remap the current directory to a project"
    )
    map_parser.add_argument("project_name")

    for command, help_text, rule_name in (
        (
            "exclude",
            "permanently exclude paths from synchronization",
            "exclusion",
        ),
        (
            "include",
            "permanently re-include paths in synchronization",
            "inclusion",
        ),
    ):
        rules_parser = subparsers.add_parser(command, help=help_text)
        add_pattern_operands(
            rules_parser,
            required=False,
            help_text=(
                "HLS path patterns or comma-separated pattern groups "
                f"relative to the local root; omit to list {rule_name} rules"
            ),
        )
        rules_parser.add_argument(
            "--project",
            dest="project_name",
            help="project name; inferred from the current directory when omitted",
        )

    tracked_parser = subparsers.add_parser(
        "tracked", help="list local files eligible for synchronization"
    )
    tracked_parser.add_argument(
        "--project",
        dest="project_name",
        help="project name; inferred from the current directory when omitted",
    )

    rules_parser = subparsers.add_parser(
        "rules", help="list or remove synchronization rules"
    )
    rules_parser.add_argument("operation", nargs="?", choices=("remove",))
    rules_parser.add_argument("rule_id", nargs="?", type=int)
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

    diff_parser = subparsers.add_parser(
        "diff",
        help="preview file changes without modifying anything",
        description=(
            "Preview file changes without modifying local or remote files. "
            "Shows the local perspective by default; use --pull for the remote "
            "perspective."
        ),
    )
    add_pattern_operands(
        diff_parser,
        required=False,
        help_text=(
            "relative file paths or wildcard patterns; defaults to the whole project"
        ),
    )
    diff_parser.add_argument(
        "--project",
        dest="project_name",
        help="project name; inferred from the current directory when omitted",
    )
    diff_parser.add_argument(
        "--pull",
        action="store_true",
        help="show changes from the remote perspective",
    )
    diff_parser.add_argument(
        "-p",
        "--prune-remote",
        action="store_true",
        help="project deletion of remote-only paths",
    )
    diff_parser.add_argument(
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


def _confirm(
    prompt: str,
    stdin: TextIO,
    stdout: TextIO,
    *,
    default: bool,
) -> bool:
    while True:
        print(prompt, end="", file=stdout, flush=True)
        answer = stdin.readline()
        if answer == "":
            raise ConfigurationError("confirmation requires yes or no")
        normalized = answer.strip().lower()
        if normalized in {"y", "yes"}:
            return True
        if normalized in {"n", "no"}:
            return False
        if normalized == "":
            return default
        print("Please answer yes or no.", file=stdout)


def _save_project(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    stdin: TextIO,
    stdout: TextIO,
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
    local_root = canonical_local_root(Path.cwd())
    prompt = (
        f"Map current directory '{local_root}' to "
        f"'{name}:{project.remote_root}'? [Y/n] "
    )
    if _confirm(prompt, stdin, stdout, default=True):
        configuration.map_project(name, local_root)
        message = (
            f"Added FTPS project '{name}'.\n"
            f"Mapped '{local_root}' to '{name}:{project.remote_root}'."
        )
    else:
        message = f"Added FTPS project '{name}' without a local mapping."
    store.save(configuration)
    return message


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


def _map(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    stdin: TextIO,
    stdout: TextIO,
) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    local_root = canonical_local_root(Path.cwd())
    if project.local_root == local_root:
        return f"Project '{name}' is already mapped to '{local_root}'."
    if project.local_root is not None:
        prompt = (
            f"Project '{name}' is mapped to '{project.local_root}'. Change it "
            f"to '{local_root}'? [y/N] "
        )
        if not _confirm(prompt, stdin, stdout, default=False):
            return f"Kept existing mapping '{project.local_root}' for '{name}'."
        configuration.remap_project(name, local_root)
        store.save(configuration)
        return (
            f"Remapped '{name}' from '{project.local_root}' "
            f"to '{local_root}'."
        )
    configuration.map_project(name, local_root)
    store.save(configuration)
    return f"Mapped '{local_root}' to '{name}:{project.remote_root}'."


def _format_rules(
    name: str,
    rules: tuple[SyncRule, ...],
    *,
    heading: str,
) -> str:
    if not rules:
        return f"No {heading.lower()} for project '{name}'."
    width = len(str(rules[-1].id))
    return "\n".join(
        (
            f"{heading} for project '{name}':",
            *(
                f"  {rule.id:>{width}}  {rule.action:<7} {rule.pattern}"
                for rule in rules
            ),
        )
    )


def _change_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    *,
    include: bool,
) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    patterns = normalize_pattern_operands(arguments)
    if not patterns:
        action = "include" if include else "exclude"
        rules = tuple(rule for rule in project.rules if rule.action == action)
        kind = "Inclusion" if include else "Exclusion"
        return _format_rules(name, rules, heading=f"{kind} rules")
    root = _require_local_root(name, project)
    normalized = patterns_from_operands(
        patterns,
        project_root=root,
        current_directory=Path.cwd().resolve(strict=True),
    )
    added = configuration.append_rules(
        name,
        "include" if include else "exclude",
        normalized,
    )
    store.save(configuration)
    action = "Inclusion" if include else "Exclusion"
    return _format_rules(
        name,
        added,
        heading=f"Recorded {action.lower()} rules",
    )


def _list_tracked_files(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    snapshot = snapshot_local(
        root,
        RuleSet(project.rules),
        include_excluded=True,
    )
    paths = tuple(
        entry.path
        for entry in snapshot.entries
        if entry.kind == "file" and not entry.excluded
    )
    if not paths:
        return f"No tracked local files for project '{name}'."
    return "\n".join(
        (
            f"Tracked local files for project '{name}':",
            *(f"  {path}" for path in paths),
        )
    )


def _manage_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    if arguments.operation is None:
        if arguments.rule_id is not None:
            raise ConfigurationError("a rule id requires the remove operation")
        return _format_rules(name, project.rules, heading="Synchronization rules")
    if arguments.rule_id is None:
        raise ConfigurationError("rules remove requires a rule id")
    removed = configuration.remove_rule(name, arguments.rule_id)
    store.save(configuration)
    return (
        f"Removed rule {removed.id} from project '{name}': "
        f"{removed.action} {removed.pattern}"
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
        if project.rules:
            lines.append("  Rules:")
            width = len(str(project.rules[-1].id))
            lines.extend(
                f"    {rule.id:>{width}}  {rule.action:<7} {rule.pattern}"
                for rule in project.rules
            )
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
    snapshot = snapshot_local(root, RuleSet(project.rules))
    return _format_snapshot("Local", name, snapshot)


def _list_remote(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    _, name, project = _resolve_project(arguments, store)
    _require_local_root(name, project)
    with ExplicitFTPSTransport(project) as transport:
        snapshot = transport.snapshot(RuleSet(project.rules))
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


def _comparison_entry_kind(entry: ComparisonEntry, direction: str) -> str:
    selected = entry.local_kind if direction == "push" else entry.remote_kind
    return selected or entry.remote_kind or entry.local_kind or "unknown"


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
        directory = _comparison_entry_kind(entry, plan.direction) == "directory"
        kind = "d" if directory else " "
        line = f"{marker} {kind} {entry.path}"
        if not color:
            lines.append(line)
        elif directory:
            directory_color = "\033[34m" if entry.action == "excluded" else "\033[94m"
            lines.append(
                f"{colors[marker]}{marker}\033[0m "
                f"{directory_color}d {entry.path}\033[0m"
            )
        else:
            lines.append(f"{colors[marker]}{line}\033[0m")
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
    rules = RuleSet(project.rules)
    selector = _file_selection(arguments, root)
    print("Scanning local files...", file=progress, flush=True)
    local = snapshot_local(
        root,
        rules,
        selector,
        include_excluded=include_excluded,
    )
    print("Reading remote files over FTPS...", file=progress, flush=True)
    remote = transport.snapshot(
        rules,
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


def _diff(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    progress: TextIO,
    output: TextIO,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    print(f"Checking differences for project '{name}'...", file=progress, flush=True)
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
    stdin: TextIO = sys.stdin,
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
            message = _save_project(arguments, configuration_store, stdin, stdout)
        elif arguments.command == "connect":
            message = _connect(arguments, configuration_store)
        elif arguments.command == "map":
            message = _map(arguments, configuration_store, stdin, stdout)
        elif arguments.command == "exclude":
            message = _change_rules(
                arguments, configuration_store, include=False
            )
        elif arguments.command == "include":
            message = _change_rules(arguments, configuration_store, include=True)
        elif arguments.command == "tracked":
            message = _list_tracked_files(arguments, configuration_store)
        elif arguments.command == "rules":
            message = _manage_rules(arguments, configuration_store)
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
        elif arguments.command == "diff":
            message = _diff(arguments, configuration_store, stderr, stdout)
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
        RuleError,
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

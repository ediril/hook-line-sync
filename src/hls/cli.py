from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
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
from hls.rules import (
    RuleError,
    RuleSet,
    SyncRule,
    expand_path_operands,
    patterns_from_operands,
)
from hls.selection import FileSelection, FileSelector, FileSelectorSet, SelectionError
from hls.snapshot import (
    SnapshotError,
    TreeSnapshot,
    list_local_directory,
    snapshot_local,
)
from hls.transfer import TransferError, TransferResult, execute_transfer
from hls.transport import ExplicitFTPSTransport, TransportError

CANONICAL_COMMANDS = (
    "add",
    "connect",
    "map",
    "remove",
    "profile",
    "profiles",
    "list",
    "diff",
    "push",
    "pull",
    "exclude",
    "include",
    "rules",
    "help",
    "version",
)
COMMAND_ALIASES = {"ls": "list"}


def _resolve_command_name(
    value: str,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> str:
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
        is_terminal = getattr(stdin, "isatty", None)
        if stdin is not None and stdout is not None and is_terminal and is_terminal():
            print(f"'{value}' matches multiple commands:\n", file=stdout)
            for index, command in enumerate(matches, start=1):
                print(f"  {index}. {command}", file=stdout)
            while True:
                print(
                    f"\nChoose a command [1-{len(matches)}]: ",
                    end="",
                    file=stdout,
                    flush=True,
                )
                answer = stdin.readline()
                if answer == "":
                    raise ConfigurationError("command selection cancelled")
                try:
                    selection = int(answer.strip())
                except ValueError:
                    selection = 0
                if 1 <= selection <= len(matches):
                    return matches[selection - 1]
                print("Enter one of the listed numbers.", file=stdout)
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
        rules_parser = subparsers.add_parser(
            command,
            help=help_text,
            usage=(
                f"hls {command} [PATH ...] [--project PROJECT_NAME]\n"
                f"       hls {command} --pattern PATTERN ... "
                "[--project PROJECT_NAME]"
            ),
        )
        add_pattern_operands(
            rules_parser,
            required=False,
            metavar="PATH",
            help_text=(
                "local paths, wildcard expressions, or comma-separated groups; "
                f"omit to list {rule_name} rules"
            ),
        )
        rules_parser.add_argument(
            "--pattern",
            action="store_true",
            help="record operands as reusable wildcard patterns",
        )
        rules_parser.add_argument(
            "--project",
            dest="project_name",
            help="project name; inferred from the current directory when omitted",
        )

    rules_parser = subparsers.add_parser(
        "rules",
        help="list or remove synchronization rules",
        usage=(
            "hls rules [--project PROJECT_NAME]\n"
            "       hls rules remove RULE_ID [--project PROJECT_NAME]"
        ),
        description=(
            "List synchronization rules, or remove one rule by its numeric ID."
        ),
    )
    rules_parser.add_argument(
        "operation",
        nargs="?",
        choices=("remove",),
        metavar="remove",
        help="remove one rule; omit to list rules",
    )
    rules_parser.add_argument(
        "rule_id",
        nargs="?",
        type=int,
        metavar="RULE_ID",
        help="numeric rule ID required by remove",
    )
    rules_parser.add_argument(
        "--project",
        dest="project_name",
        help="project name; inferred from the current directory when omitted",
    )

    remove_parser = subparsers.add_parser("remove", help="remove a project")
    remove_parser.add_argument("project_name")

    profile_parser = subparsers.add_parser(
        "profile", help="show details for one profile"
    )
    profile_parser.add_argument(
        "project_name",
        nargs="?",
        metavar="PROFILE",
        help="profile name; inferred from the current directory when omitted",
    )

    subparsers.add_parser("profiles", help="list configured profiles")

    list_parser = subparsers.add_parser(
        "list",
        help="list the mapped local tree and exclusion status",
        description=(
            "List selected paths in the mapped local tree, including exclusion "
            "status, without connecting to FTPS."
        ),
    )
    add_pattern_operands(
        list_parser,
        required=False,
        help_text=(
            "relative file paths or wildcard patterns; defaults to the whole project"
        ),
    )
    list_parser.add_argument(
        "--project",
        dest="project_name",
        help="project name; inferred from the current directory when omitted",
    )
    list_parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="color paths; defaults to auto detection",
    )

    diff_parser = subparsers.add_parser(
        "diff",
        help="preview file changes without modifying anything",
        usage=(
            "hls diff [PATH ...] [--project PROFILE]\n"
            "       [--pull | --prune-remote] [--all] [--paged]\n"
            "       [--resume DIRECTORY] [--color auto|always|never]"
        ),
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
    diff_direction = diff_parser.add_mutually_exclusive_group()
    diff_direction.add_argument(
        "--pull",
        action="store_true",
        help="show changes from the remote perspective; cannot prune",
    )
    diff_parser.add_argument(
        "--all",
        action="store_true",
        help="also show unchanged and excluded paths",
    )
    diff_parser.add_argument(
        "--paged",
        action="store_true",
        help="show one directory, then exit with a resume command",
    )
    diff_parser.add_argument(
        "--resume",
        metavar="DIRECTORY",
        help="resume a paged diff at a project-relative directory",
    )
    diff_direction.add_argument(
        "-p",
        "--prune-remote",
        action="store_true",
        help="project deletion of remote-only paths in the push view",
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
        transfer_parser.set_defaults(prune_remote=False)
        if command == "push":
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
                f"  {rule.id:>{width}}  {rule.action:<7} "
                f"{_format_rule_expression(rule)}"
                for rule in rules
            ),
        )
    )


def _format_rule_expression(rule: SyncRule) -> str:
    return rule.pattern if "*" in rule.pattern else f"./{rule.pattern}"


def _change_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    *,
    include: bool,
) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    patterns = normalize_pattern_operands(arguments)
    if not patterns:
        if arguments.pattern:
            raise ConfigurationError("--pattern requires at least one operand")
        action = "include" if include else "exclude"
        rules = tuple(rule for rule in project.rules if rule.action == action)
        kind = "Inclusion" if include else "Exclusion"
        return _format_rules(name, rules, heading=f"{kind} rules")
    root = _require_local_root(name, project)
    current_directory = Path.cwd().resolve(strict=True)
    operands = (
        patterns
        if arguments.pattern
        else expand_path_operands(
            patterns,
            project_root=root,
            current_directory=current_directory,
        )
    )
    normalized = patterns_from_operands(
        operands,
        project_root=root,
        current_directory=current_directory,
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
        f"{removed.action} {_format_rule_expression(removed)}"
    )


def _remove(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, _ = _resolve_project(arguments, store)
    del configuration.projects[name]
    store.save(configuration)
    return f"Removed project '{name}'."


def _list_profiles(store: ConfigurationStore) -> str:
    configuration = store.load()
    if not configuration.projects:
        return "No profiles configured."

    active = configuration.project_for_path(Path.cwd().resolve(strict=True))
    active_name = active[0] if active is not None else None
    return "\n".join(
        f"{'*' if name == active_name else ' '} {name}"
        for name in sorted(configuration.projects)
    )


def _show_profile(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    return "\n".join(
        (
            f"Profile '{name}':",
            f"  Protocol: {project.type.upper()}",
            f"  Host: {project.host}:{project.port}",
            f"  Remote root: {project.remote_root}",
            f"  Local root: {project.local_root or 'not mapped'}",
            f"  Username env: {project.username_env}",
            f"  Password env: {project.password_env}",
            f"  Rules: {len(project.rules)}",
        )
    )


def _require_local_root(name: str, project: ProjectConfiguration) -> Path:
    if project.local_root is None:
        raise ConfigurationError(f"project '{name}' has not been mapped")
    return Path(project.local_root)


def _list_local(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    output: TextIO,
) -> str:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    selector = _file_selection(arguments, root)
    snapshot = snapshot_local(
        root,
        RuleSet(project.rules),
        selector,
        include_excluded=True,
    )
    if selector is not None and not snapshot.entries:
        raise SelectionError(f"file selector '{selector.pattern}' matched no paths")
    if not snapshot.entries:
        return f"Local tree for project '{name}' is empty."
    lines = [f"Local tree for project '{name}':"]
    color = _use_color(arguments.color, output)
    for entry in snapshot.entries:
        marker = "x" if entry.excluded else " "
        lines.append(
            _format_path_line(
                marker,
                directory=entry.kind == "directory",
                path=entry.path,
                color=color,
                marker_color="\033[90m" if entry.excluded else None,
                excluded=entry.excluded,
            )
        )
    return "\n".join(lines)


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
        return "!"
    if entry.action == "conflict":
        return "?"
    if entry.action == "unchanged":
        return "="
    if entry.action == "skip":
        return "·"
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


def _format_path_line(
    marker: str,
    *,
    directory: bool,
    path: str,
    color: bool,
    marker_color: str | None,
    excluded: bool,
) -> str:
    kind = "d" if directory else " "
    line = f"{marker} {kind} {path}"
    if not color:
        return line
    if directory:
        directory_color = "\033[34m" if excluded else "\033[94m"
        colored_marker = (
            f"{marker_color}{marker}\033[0m" if marker_color else marker
        )
        return f"{colored_marker} {directory_color}d {path}\033[0m"
    if marker_color:
        return f"{marker_color}{line}\033[0m"
    return line


def _format_comparison_entries(
    entries: Sequence[ComparisonEntry],
    direction: str,
    *,
    color: bool,
) -> tuple[str, ...]:
    lines: list[str] = []
    colors = {
        "+": "\033[32m",
        "~": "\033[33m",
        "-": "\033[31m",
        "?": "\033[35m",
        "=": "\033[90m",
        "!": "\033[90m",
        "·": "\033[90m",
    }
    for entry in entries:
        marker = _comparison_marker(entry, direction)
        directory = _comparison_entry_kind(entry, direction) == "directory"
        lines.append(
            _format_path_line(
                marker,
                directory=directory,
                path=entry.path,
                color=color,
                marker_color=colors[marker],
                excluded=entry.action == "excluded",
            )
        )
    return tuple(lines)


def _file_selection(arguments: argparse.Namespace, root: Path) -> FileSelection | None:
    current_directory = Path.cwd().resolve(strict=True)
    values = [
        "**" if value == "." else value
        for value in normalize_pattern_operands(arguments)
    ]
    selectors = tuple(
        FileSelector.from_argument(
            value,
            project_root=root,
            current_directory=current_directory,
        )
        for value in values
    )
    if not selectors:
        return None
    if len(selectors) == 1:
        return selectors[0]
    return FileSelectorSet(selectors)


def _filtered_listing(
    listing: TreeSnapshot,
    selector: FileSelection | None,
    *,
    include_all: bool,
) -> TreeSnapshot:
    return TreeSnapshot(
        tuple(
            entry
            for entry in listing.entries
            if (include_all or not entry.excluded)
            and (selector is None or selector.matches(entry.path))
        )
    )


def _descendant_directories(
    local: TreeSnapshot,
    remote: TreeSnapshot,
    rules: RuleSet,
    selector: FileSelection | None,
    *,
    include_all: bool,
) -> tuple[tuple[PurePosixPath, bool, bool], ...]:
    local_directories = {
        entry.path: entry for entry in local.entries if entry.kind == "directory"
    }
    remote_directories = {
        entry.path: entry for entry in remote.entries if entry.kind == "directory"
    }
    paths = sorted(local_directories.keys() | remote_directories.keys())
    return tuple(
        (
            PurePosixPath(path),
            path in local_directories,
            path in remote_directories,
        )
        for path in paths
        for entry in (local_directories.get(path) or remote_directories[path],)
        if (selector is None or selector.may_match_descendant(path))
        and (
            include_all
            or not entry.excluded
            or rules.may_include_descendant(path)
        )
    )


def _resume_directory(value: str | None) -> PurePosixPath | None:
    if value is None:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SelectionError(
            "resume directory must be a project-relative directory"
        )
    if any(character in value for character in "*?["):
        raise SelectionError("resume directory cannot contain wildcards")
    return path


def _resume_command(arguments: argparse.Namespace, directory: PurePosixPath) -> str:
    command = ["hls", "diff", *arguments.pattern_operands]
    if arguments.project_name is not None:
        command.extend(("--project", arguments.project_name))
    if arguments.pull:
        command.append("--pull")
    if arguments.prune_remote:
        command.append("--prune-remote")
    if arguments.all:
        command.append("--all")
    if arguments.color != "auto":
        command.extend(("--color", arguments.color))
    command.extend(("--paged", "--resume", directory.as_posix()))
    return shlex.join(command)


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
) -> None:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    if arguments.resume is not None and not arguments.paged:
        raise ConfigurationError("--resume requires --paged")
    resume = _resume_directory(arguments.resume)
    selector = _file_selection(arguments, root)
    rules = RuleSet(project.rules)
    direction = "pull" if arguments.pull else "push"
    perspective = "Local -> Remote" if direction == "push" else "Remote -> Local"
    color = _use_color(arguments.color, output)
    print(f"Checking differences for project '{name}'...", file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    pending = [(PurePosixPath(), True, True)]
    seeking = resume is not None
    selected_count = 0
    displayed_count = 0
    with ExplicitFTPSTransport(project) as transport:
        print(f"{perspective} for project '{name}':", file=output, flush=True)
        while pending:
            directory, has_local, has_remote = pending.pop()
            display_directory = directory.as_posix()
            print(
                f"Comparing directory '{display_directory}'...",
                file=progress,
                flush=True,
            )
            local_listing = (
                list_local_directory(root, directory, rules)
                if has_local
                else TreeSnapshot()
            )
            remote_listing = (
                transport.list_directory(directory, rules)
                if has_remote
                else TreeSnapshot()
            )
            descendants = _descendant_directories(
                local_listing,
                remote_listing,
                rules,
                selector,
                include_all=arguments.all,
            )

            if seeking and directory != resume:
                assert resume is not None
                current_parts = directory.parts
                if resume.parts[: len(current_parts)] != current_parts:
                    raise SelectionError(
                        f"resume directory '{resume}' is not reachable"
                    )
                branch_length = len(current_parts) + 1
                branch = PurePosixPath(*resume.parts[:branch_length])
                matching_branch = next(
                    (candidate for candidate in descendants if candidate[0] == branch),
                    None,
                )
                if matching_branch is None:
                    raise SelectionError(
                        f"resume directory '{resume}' is not reachable"
                    )
                later = tuple(
                    candidate for candidate in descendants if candidate[0] > branch
                )
                pending.extend(reversed(later))
                pending.append(matching_branch)
                continue

            seeking = False
            pending.extend(reversed(descendants))
            local = _filtered_listing(
                local_listing,
                selector,
                include_all=arguments.all,
            )
            remote = _filtered_listing(
                remote_listing,
                selector,
                include_all=arguments.all,
            )
            selected_count += len(local.entries) + len(remote.entries)
            plan = build_comparison(
                local,
                remote,
                direction=direction,
                prune_remote=arguments.prune_remote,
            )
            shown = (
                plan.entries
                if arguments.all
                else tuple(
                    entry
                    for entry in plan.entries
                    if entry.action not in {"unchanged", "excluded"}
                )
            )
            lines = _format_comparison_entries(shown, direction, color=color)
            for line in lines:
                print(line, file=output, flush=True)
            displayed_count += len(lines)

            if arguments.paged:
                if not lines:
                    label = "entries" if arguments.all else "changes"
                    print(
                        f"  no {label} in {display_directory}",
                        file=output,
                        flush=True,
                    )
                if pending:
                    print(
                        f"Resume: {_resume_command(arguments, pending[-1][0])}",
                        file=output,
                        flush=True,
                    )
                return

    if seeking:
        assert resume is not None
        raise SelectionError(f"resume directory '{resume}' is not reachable")
    if selector is not None and selected_count == 0:
        raise SelectionError(f"file selector '{selector.pattern}' matched no paths")
    if displayed_count == 0:
        print("  no differences", file=output, flush=True)


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


def _show_help(
    parser: argparse.ArgumentParser,
    topic: str | None,
    stdin: TextIO,
    stdout: TextIO,
) -> str:
    if topic is None:
        return parser.format_help().rstrip()
    subparser = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    resolved = _resolve_command_name(topic, stdin=stdin, stdout=stdout)
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
            raw_arguments[0] = _resolve_command_name(
                raw_arguments[0],
                stdin=stdin,
                stdout=stdout,
            )
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
        elif arguments.command == "rules":
            message = _manage_rules(arguments, configuration_store)
        elif arguments.command == "remove":
            message = _remove(arguments, configuration_store)
        elif arguments.command == "profile":
            message = _show_profile(arguments, configuration_store)
        elif arguments.command == "profiles":
            message = _list_profiles(configuration_store)
        elif arguments.command == "list":
            message = _list_local(arguments, configuration_store, stdout)
        elif arguments.command == "diff":
            _diff(arguments, configuration_store, stderr, stdout)
            message = None
        elif arguments.command in {"push", "pull"}:
            message = _transfer(arguments, configuration_store, stderr)
        elif arguments.command == "help":
            message = _show_help(parser, arguments.topic, stdin, stdout)
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
    if message is not None:
        print(message, file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

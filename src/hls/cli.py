from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TextIO, TypeVar

from hls import __version__
from hls.comparison import (
    ComparisonEntry,
    ComparisonPlan,
    build_comparison,
    mark_untraversed_directories,
)
from hls.config import (
    DEFAULT_PASSWORD_ENV,
    DEFAULT_USERNAME_ENV,
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    ProjectConfiguration,
    RuleUpdate,
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
from hls.selection import (
    DirectoryContentsSelection,
    FileSelection,
    FileSelector,
    FileSelectorSet,
    SelectionError,
)
from hls.snapshot import (
    SnapshotError,
    TreeEntry,
    TreeSnapshot,
    list_local_directory,
    snapshot_local,
)
from hls.transfer import (
    TransferError,
    TransferOperation,
    TransferResult,
    execute_transfer,
)
from hls.transport import ExplicitFTPSTransport, PathOperationError, TransportError

_EntryT = TypeVar("_EntryT")

_RESET = "\033[0m"
_DIRECTORY_COLOR = "\033[38;5;75m"
_EXCLUDED_DIRECTORY_COLOR = "\033[38;5;24m"
_COLLAPSED_DIRECTORY_COLOR = "\033[3;38;5;24m"
_EXCLUDED_REMOTE_COLOR = "\033[38;5;166m"
_DIFF_MARKER_COLORS = {
    "+": "\033[38;5;82m",
    "~": "\033[33m",
    "-": "\033[31m",
    "?": "\033[35m",
    "x": "\033[90m",
    "!": _EXCLUDED_REMOTE_COLOR,
    "r": "\033[38;5;30m",
    "l": "\033[38;5;51m",
}


@dataclass(frozen=True)
class _DiffTraversalRoot:
    path: PurePosixPath
    include_container: bool = False


@dataclass(frozen=True)
class _PendingDiffDirectory:
    path: PurePosixPath
    has_local: bool
    has_remote: bool
    include_container: bool
    is_root: bool
    display_root: PurePosixPath | None
    display_anchor: bool

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
PROFILE_AWARE_COMMANDS = frozenset(
    {
        "connect",
        "map",
        "remove",
        "profile",
        "list",
        "diff",
        "push",
        "pull",
        "exclude",
        "include",
        "rules",
    }
)


def _add_included_only_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-i",
        "--inc",
        "--included-only",
        dest="included_only",
        action="store_true",
        help="show only included paths",
    )


def _active_options(arguments: argparse.Namespace) -> str | None:
    options: list[str] = []
    if getattr(arguments, "pull", False):
        options.append("pull perspective (--pull)")
    if getattr(arguments, "recursive", False):
        options.append("recursive (-r)")
    if getattr(arguments, "included_only", False):
        options.append("included paths only (-i)")
    if getattr(arguments, "prune_remote", False):
        label = (
            "preview remote pruning (-p)"
            if arguments.command == "diff"
            else "remote pruning (-p)"
        )
        options.append(label)
    if getattr(arguments, "paged", False):
        options.append("paged output (--paged)")
    if getattr(arguments, "resume", None) is not None:
        options.append(f"resume at {arguments.resume!r} (--resume)")
    if not options:
        return None
    return f"Options: {'; '.join(options)}."


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


def _could_be_command(value: str) -> bool:
    return value in COMMAND_ALIASES or any(
        command.startswith(value) for command in CANONICAL_COMMANDS
    )


def _resolve_invocation(
    raw_arguments: list[str],
    *,
    stdin: TextIO,
    stdout: TextIO,
) -> tuple[list[str], str | None]:
    if not raw_arguments or raw_arguments[0].startswith("-"):
        return raw_arguments, None
    first = raw_arguments[0]
    if (
        first not in CANONICAL_COMMANDS
        and first not in COMMAND_ALIASES
        and len(raw_arguments) > 1
        and not raw_arguments[1].startswith("-")
        and _could_be_command(raw_arguments[1])
    ):
        profile_name = validate_project_name(first)
        raw_arguments = raw_arguments[1:]
        raw_arguments[0] = _resolve_command_name(
            raw_arguments[0], stdin=stdin, stdout=stdout
        )
        return raw_arguments, profile_name
    raw_arguments[0] = _resolve_command_name(first, stdin=stdin, stdout=stdout)
    return raw_arguments, None


def _validate_profile_prefix(arguments: argparse.Namespace) -> None:
    profile_name = getattr(arguments, "profile_prefix", None)
    if profile_name is not None and arguments.command not in PROFILE_AWARE_COMMANDS:
        raise ConfigurationError(
            f"profile prefix '{profile_name}' cannot be used with "
            f"'{arguments.command}'"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hlsync",
        description=(
            "Transfer mapped files over explicit FTP over TLS. Prefix a command "
            "with a profile to use that profile's local root as the working "
            "directory. Commands may be shortened to any unique prefix."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--legend",
        action="store_true",
        help="show diff symbols and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

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
        "connect",
        help="verify a project's FTPS connection",
        usage="hlsync connect [PROFILE]\n       hlsync PROFILE connect",
    )
    connect_parser.add_argument("project_name", nargs="?")

    map_parser = subparsers.add_parser(
        "map",
        help="map or remap the current directory to a project",
        usage="hlsync map [PROFILE]\n       hlsync PROFILE map",
    )
    map_parser.add_argument("project_name", nargs="?")

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
                f"hlsync [PROFILE] {command} [PATH ...]\n"
                f"       hlsync [PROFILE] {command} --pattern PATTERN ..."
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

    rules_parser = subparsers.add_parser(
        "rules",
        help="list or remove synchronization rules",
        usage=(
            "hlsync [PROFILE] rules\n"
            "       hlsync [PROFILE] rules remove RULE_ID"
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
    remove_parser = subparsers.add_parser(
        "remove",
        help="remove a project",
        usage="hlsync remove [PROFILE]\n       hlsync PROFILE remove",
    )
    remove_parser.add_argument("project_name", nargs="?")

    profile_parser = subparsers.add_parser(
        "profile",
        help="show details for one profile",
        usage="hlsync profile [PROFILE]\n       hlsync PROFILE profile",
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
        help="list the current local directory and exclusion status",
        usage="hlsync [PROFILE] list [-r] [-i] [PATH ...]",
        description=(
            "List selected paths in the current mapped local directory, "
            "including dotfiles and exclusion status, without connecting to FTPS."
        ),
    )
    add_pattern_operands(
        list_parser,
        required=False,
        help_text=(
            "relative file paths or wildcard patterns; defaults to immediate "
            "contents of the current directory"
        ),
    )
    list_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="include descendants of the selected directories",
    )
    _add_included_only_argument(list_parser)

    diff_parser = subparsers.add_parser(
        "diff",
        help="preview file changes without modifying anything",
        usage=(
            "hlsync [PROFILE] diff [PATH ...]\n"
            "       [--pull | --prune-remote] [-r] [-i] [--paged]\n"
            "       [--resume DIRECTORY]"
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
            "relative file paths or wildcard patterns; defaults to immediate "
            "contents of the current directory"
        ),
    )
    diff_direction = diff_parser.add_mutually_exclusive_group()
    diff_direction.add_argument(
        "--pull",
        action="store_true",
        help="show changes from the remote perspective; cannot prune",
    )
    diff_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="include descendants of selected directories",
    )
    _add_included_only_argument(diff_parser)
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
            usage=(
                f"hlsync [PROFILE] {command} [PATH ...] [-r]"
                + (" [-p]" if command == "push" else "")
            ),
        )
        add_pattern_operands(
            transfer_parser,
            required=command == "pull",
            metavar="PATH",
            help_text=(
                "relative file paths or wildcard patterns; defaults to the "
                "complete current subtree"
                if command == "push"
                else "required relative file paths or wildcard patterns"
            ),
        )
        transfer_parser.add_argument(
            "-r",
            "--recursive",
            action="store_true",
            help=(
                "include descendants of explicit selected directories; bare "
                "push is already recursive"
                if command == "push"
                else "include descendants of selected directories"
            ),
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
    prefix_name = getattr(arguments, "profile_prefix", None)
    positional_name = getattr(arguments, "project_name", None)
    if prefix_name is not None and positional_name is not None:
        raise ConfigurationError(
            "profile was specified both before the command and as an argument"
        )
    supplied_name = prefix_name or positional_name
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


def _effective_current_directory(
    arguments: argparse.Namespace,
    project_root: Path,
) -> Path:
    if getattr(arguments, "profile_prefix", None) is not None:
        return project_root.resolve(strict=True)
    return Path.cwd().resolve(strict=True)


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
    grouped: bool = False,
) -> str:
    if not rules:
        return f"No {heading.lower()} for project '{name}'."
    width = len(str(max(rule.id for rule in rules)))
    if grouped:
        groups: dict[str, list[tuple[SyncRule, str]]] = {}
        for rule in rules:
            group, expression = _rule_display_location(rule)
            groups.setdefault(group, []).append((rule, expression))
        lines = [f"{heading} for project '{name}':"]
        for group in sorted(groups, key=_rule_group_key):
            lines.extend(("", group))
            for rule, expression in sorted(
                groups[group],
                key=lambda item: (item[1].casefold(), item[1], item[0].id),
            ):
                lines.append(
                    f"  {rule.id:>{width}}  {rule.action:<7} {expression}"
                )
        if _rules_need_precedence_note(rules):
            lines.extend(("", "Higher rule IDs take precedence when rules overlap."))
        return "\n".join(lines)
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


def _rule_display_location(rule: SyncRule) -> tuple[str, str]:
    parts = PurePosixPath(rule.pattern).parts
    wildcard_index = next(
        (index for index, part in enumerate(parts) if "*" in part),
        None,
    )
    if wildcard_index is None:
        parent = parts[:-1]
        return _rule_group_label(parent), parts[-1]
    if wildcard_index == 0 and parts[0] == "**":
        expression = "/".join(parts[1:]) or "all contents"
        return "Everywhere", expression
    parent = parts[:wildcard_index]
    expression = "/".join(parts[wildcard_index:])
    if expression == "**":
        expression = "all contents"
    return _rule_group_label(parent), expression


def _rule_group_label(parts: tuple[str, ...]) -> str:
    return "./" if not parts else f"{PurePosixPath(*parts).as_posix()}/"


def _rule_group_key(group: str) -> tuple[int, str, str]:
    if group == "./":
        return (0, "", "")
    if group == "Everywhere":
        return (2, "", "")
    return (1, group.casefold(), group)


def _rules_need_precedence_note(rules: tuple[SyncRule, ...]) -> bool:
    return len({rule.action for rule in rules}) > 1


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
        return _format_rules(name, rules, heading=f"{kind} rules", grouped=True)
    root = _require_local_root(name, project)
    current_directory = _effective_current_directory(arguments, root)
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
    update = configuration.append_rules(
        name,
        "include" if include else "exclude",
        normalized,
    )
    store.save(configuration)
    return _format_rule_update(name, update, include=include)


def _format_rule_update(name: str, update: RuleUpdate, *, include: bool) -> str:
    if update.added and update.removed:
        lines = [f"Updated synchronization rules for project '{name}':"]
        lines.extend(
            f"  added    {rule.id}  {rule.action:<7} {_format_rule_expression(rule)}"
            for rule in update.added
        )
        lines.extend(
            f"  removed  {rule.id}  {rule.action:<7} {_format_rule_expression(rule)}"
            for rule in update.removed
        )
        return "\n".join(lines)
    if update.added:
        action = "Inclusion" if include else "Exclusion"
        return _format_rules(
            name,
            update.added,
            heading=f"Recorded {action.lower()} rules",
        )
    if update.removed:
        result = "included" if include else "excluded"
        lines = [
            f"Paths are {result} by the remaining policy for project '{name}';",
            "removed the unnecessary rules:",
        ]
        width = len(str(max(rule.id for rule in update.removed)))
        lines.extend(
            f"  {rule.id:>{width}}  {rule.action:<7} {_format_rule_expression(rule)}"
            for rule in update.removed
        )
        return "\n".join(lines)
    return f"Synchronization rules for project '{name}' are unchanged."


def _manage_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    configuration, name, project = _resolve_project(arguments, store)
    if arguments.operation is None:
        if arguments.rule_id is not None:
            raise ConfigurationError("a rule id requires the remove operation")
        return _format_rules(
            name,
            project.rules,
            heading="Synchronization rules",
            grouped=True,
        )
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
    selector = _list_selection(arguments, root)
    raw_snapshot = snapshot_local(
        root,
        RuleSet(project.rules),
        selector,
        include_excluded=True,
        traverse_excluded=True,
    )
    if not raw_snapshot.entries:
        raise SelectionError(f"file selector '{selector.pattern}' matched no paths")
    snapshot = TreeSnapshot(
        tuple(
            entry
            for entry in raw_snapshot.entries
            if selector.includes_result(
                entry.path,
                directory=entry.kind == "directory",
            )
            and (not arguments.included_only or not entry.excluded)
        )
    )
    if not snapshot.entries:
        return f"Local tree for project '{name}' is empty."
    lines = [f"Local tree for project '{name}':"]
    options = _active_options(arguments)
    if options is not None:
        lines.append(options)
    color = _use_color(output)
    for entry in _file_browser_order(
        snapshot.entries,
        path_of=lambda item: item.path,
        directory_of=lambda item: item.kind == "directory",
    ):
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
        return "!" if entry.remote_kind is not None else "x"
    if entry.action == "conflict":
        return "?"
    if entry.action == "unchanged":
        return "="
    if entry.action == "untraversed":
        return " "
    if entry.action == "skip":
        return "r" if entry.state == "remote-only" else "l"
    if entry.state == "changed":
        return "~"
    if direction == "push":
        return "+" if entry.state == "local-only" else "-"
    return "+" if entry.state == "remote-only" else "-"


def _comparison_entry_kind(entry: ComparisonEntry, direction: str) -> str:
    selected = entry.local_kind if direction == "push" else entry.remote_kind
    return selected or entry.remote_kind or entry.local_kind or "unknown"


def _use_color(output: TextIO) -> bool:
    if "NO_COLOR" in os.environ:
        return False
    is_terminal = getattr(output, "isatty", None)
    return bool(is_terminal and is_terminal())


def _format_legend(output: TextIO) -> str:
    color = _use_color(output)
    entries = (
        ("+", "new locally", _DIFF_MARKER_COLORS["+"]),
        ("~", "modified", _DIFF_MARKER_COLORS["~"]),
        ("-", "remote deletion authorized", _DIFF_MARKER_COLORS["-"]),
        ("r", "remote-only, retained", _DIFF_MARKER_COLORS["r"]),
        ("l", "local-only, retained", _DIFF_MARKER_COLORS["l"]),
        ("?", "conflict", _DIFF_MARKER_COLORS["?"]),
        ("=", "unchanged file", None),
        ("x", "excluded, absent remotely", _DIFF_MARKER_COLORS["x"]),
        ("!", "excluded, present remotely", _DIFF_MARKER_COLORS["!"]),
        ("/", "directory", _DIRECTORY_COLOR),
        ("▸", "contents not inspected", _COLLAPSED_DIRECTORY_COLOR),
    )
    lines = ["Diff legend:"]
    for marker, meaning, style in entries:
        rendered = f"{style}{marker}{_RESET}" if color and style else marker
        lines.append(f"  {rendered}  {meaning}")
    return "\n".join(lines)


def _format_path_line(
    marker: str,
    *,
    directory: bool,
    path: str,
    depth: int = 0,
    color: bool,
    marker_color: str | None,
    excluded: bool,
    collapsed: bool = False,
    omit_empty_directory_marker: bool = False,
    path_color: str | None = None,
) -> str:
    indent = "  " * depth
    label = f"{path}/" if directory else path
    traversal = " ▸" if collapsed else ""
    omit_marker = omit_empty_directory_marker and directory and marker == " "
    body = (
        f"{label}{traversal}"
        if omit_marker
        else f"{marker} {label}{traversal}"
    )
    line = f"{indent}{body}"
    if not color:
        return line
    if directory:
        if collapsed:
            if omit_marker:
                return f"{indent}{_COLLAPSED_DIRECTORY_COLOR}{path}/ ▸{_RESET}"
            colored_marker = (
                f"{marker_color}{marker}{_RESET}" if marker_color else marker
            )
            return (
                f"{indent}{colored_marker} "
                f"{_COLLAPSED_DIRECTORY_COLOR}{path}/ ▸{_RESET}"
            )
        directory_color = path_color or (
            _EXCLUDED_DIRECTORY_COLOR if excluded else _DIRECTORY_COLOR
        )
        if omit_marker:
            return f"{indent}{directory_color}{path}/{_RESET}"
        colored_marker = (
            f"{marker_color}{marker}{_RESET}" if marker_color else marker
        )
        return f"{indent}{colored_marker} {directory_color}{path}/{_RESET}"
    if marker_color:
        return f"{indent}{marker_color}{body}{_RESET}"
    return line


def _file_browser_order(
    entries: Sequence[_EntryT],
    *,
    path_of: Callable[[_EntryT], str],
    directory_of: Callable[[_EntryT], bool],
) -> tuple[_EntryT, ...]:
    directory_paths = {
        path_of(entry) for entry in entries if directory_of(entry)
    }

    def order_key(entry: _EntryT) -> tuple[tuple[int, str, str], ...]:
        parts = PurePosixPath(path_of(entry)).parts
        return tuple(
            (
                0
                if PurePosixPath(*parts[: index + 1]).as_posix()
                in directory_paths
                else 1,
                part.casefold(),
                part,
            )
            for index, part in enumerate(parts)
        )

    return tuple(sorted(entries, key=order_key))


def _format_comparison_entries(
    entries: Sequence[ComparisonEntry],
    direction: str,
    *,
    color: bool,
    collapsed_paths: frozenset[str] = frozenset(),
    display_path: Callable[[str], tuple[int, str]] | None = None,
) -> tuple[str, ...]:
    lines: list[str] = []
    for entry in _file_browser_order(
        entries,
        path_of=lambda item: item.path,
        directory_of=lambda item: _comparison_entry_kind(item, direction)
        == "directory",
    ):
        collapsed = entry.path in collapsed_paths
        directory = _comparison_entry_kind(entry, direction) == "directory"
        marker = (
            " "
            if directory and entry.action == "unchanged"
            else _comparison_marker(entry, direction)
        )
        remote_exclusion_color = (
            _EXCLUDED_REMOTE_COLOR
            if entry.action == "excluded" and entry.remote_kind is not None
            else None
        )
        depth, path = display_path(entry.path) if display_path else (0, entry.path)
        lines.append(
            _format_path_line(
                marker,
                directory=directory,
                path=path,
                depth=depth,
                color=color,
                marker_color=_DIFF_MARKER_COLORS.get(marker),
                excluded=entry.action == "excluded",
                collapsed=collapsed,
                omit_empty_directory_marker=True,
                path_color=remote_exclusion_color,
            )
        )
    return tuple(lines)


def _scoped_display_path(
    path: str,
    *,
    display_root: PurePosixPath | None,
) -> tuple[int, str]:
    project_path = PurePosixPath(path)
    if display_root is None:
        return 0, project_path.as_posix()
    if project_path == display_root and display_root.parts:
        return 0, display_root.as_posix()
    relative = (
        project_path.relative_to(display_root)
        if display_root.parts
        else project_path
    )
    depth = len(relative.parts) if display_root.parts else max(
        len(relative.parts) - 1,
        0,
    )
    return depth, relative.name


def _scope_header_lines(
    display_root: PurePosixPath | None,
    *,
    anchored: bool,
    color: bool,
) -> tuple[str, ...]:
    if display_root is None:
        return ()
    if anchored or not display_root.parts:
        return ()
    return (
        _format_path_line(
            " ",
            directory=True,
            path=display_root.as_posix(),
            color=color,
            marker_color=None,
            excluded=False,
            omit_empty_directory_marker=True,
        ),
    )


def _file_selection(arguments: argparse.Namespace, root: Path) -> FileSelection:
    operands = list(normalize_pattern_operands(arguments))
    current_directory = _effective_current_directory(arguments, root)
    if not operands:
        recursive = arguments.recursive or arguments.command == "push"
        return _current_directory_selection(
            root,
            current_directory=current_directory,
            recursive=recursive,
        )
    return _directory_contents_selection(
        operands,
        root,
        current_directory=current_directory,
        recursive=arguments.recursive,
    )


def _recursive_transfer_scope(arguments: argparse.Namespace) -> bool:
    return arguments.recursive or (
        arguments.command == "push"
        and not normalize_pattern_operands(arguments)
    )


def _selection_from_values(
    values: Sequence[str],
    root: Path,
    current_directory: Path,
) -> FileSelection:
    selectors = tuple(
        FileSelector.from_argument(
            value,
            project_root=root,
            current_directory=current_directory,
        )
        for value in values
    )
    if len(selectors) == 1:
        return selectors[0]
    return FileSelectorSet(selectors)


def _list_selection(
    arguments: argparse.Namespace,
    root: Path,
) -> DirectoryContentsSelection:
    operands = list(normalize_pattern_operands(arguments))
    current_directory = _effective_current_directory(arguments, root)
    if not operands:
        return _current_directory_selection(
            root,
            current_directory=current_directory,
            recursive=arguments.recursive,
        )
    return _directory_contents_selection(
        operands,
        root,
        current_directory=current_directory,
        recursive=arguments.recursive,
    )


def _current_directory_selection(
    root: Path,
    *,
    current_directory: Path,
    recursive: bool,
) -> DirectoryContentsSelection:
    pattern = "**" if recursive else "*"
    return DirectoryContentsSelection(
        _selection_from_values(
            (pattern,),
            root,
            current_directory,
        )
    )


def _directory_contents_selection(
    operands: Sequence[str],
    root: Path,
    *,
    current_directory: Path,
    recursive: bool,
) -> DirectoryContentsSelection:
    traversal_patterns: list[str] = []
    container_patterns: list[str] = []
    for operand in operands:
        if operand == ".":
            traversal_patterns.append("**" if recursive else "*")
            continue
        normalized = operand.rstrip("/")
        container_patterns.append(normalized)
        traversal_patterns.extend(
            (
                normalized,
                f"{normalized}/{'**' if recursive else '*'}",
            )
        )
    traversal = _selection_from_values(
        traversal_patterns,
        root,
        current_directory,
    )
    containers = (
        _selection_from_values(container_patterns, root, current_directory)
        if container_patterns
        else None
    )
    return DirectoryContentsSelection(traversal, containers)


def _filtered_listing(
    listing: TreeSnapshot,
    selector: FileSelection | None,
) -> TreeSnapshot:
    return TreeSnapshot(
        tuple(
            entry
            for entry in listing.entries
            if selector is None or selector.matches(entry.path)
        )
    )


def _descendant_directories(
    local: TreeSnapshot,
    remote: TreeSnapshot,
    rules: RuleSet,
    selector: FileSelection | None,
    *,
    descend_remote_only: bool,
    descend_excluded: bool,
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
        if path in local_directories or descend_remote_only
        if (selector is None or selector.may_match_descendant(path))
        and (
            not entry.excluded
            or rules.may_include_descendant(path)
            or descend_excluded
        )
    )


def _project_relative_current_directory(
    arguments: argparse.Namespace,
    root: Path,
) -> PurePosixPath:
    current = _effective_current_directory(arguments, root)
    try:
        relative = current.relative_to(root)
    except ValueError:
        return PurePosixPath()
    return PurePosixPath(*relative.parts)


def _diff_traversal_roots(
    arguments: argparse.Namespace,
    root: Path,
) -> tuple[_DiffTraversalRoot, ...]:
    """Find the narrowest deterministic directories needed by the selection."""
    base = _project_relative_current_directory(arguments, root)
    operands = normalize_pattern_operands(arguments)
    if not operands:
        return (_DiffTraversalRoot(base),)

    candidates: list[_DiffTraversalRoot] = []
    for operand in operands:
        project_path = base / PurePosixPath(operand)
        if operand == ".":
            candidates.append(_DiffTraversalRoot(base))
            continue

        wildcard_index = next(
            (
                index
                for index, part in enumerate(project_path.parts)
                if "*" in part
            ),
            None,
        )
        if wildcard_index is not None:
            fixed_parts = project_path.parts[:wildcard_index]
            fixed = PurePosixPath(*fixed_parts) if fixed_parts else PurePosixPath()
            candidates.append(_DiffTraversalRoot(fixed))
            continue

        local_path = root.joinpath(*project_path.parts)
        if local_path.is_dir() and not local_path.is_symlink():
            candidates.append(_DiffTraversalRoot(project_path, include_container=True))
        else:
            candidates.append(_DiffTraversalRoot(project_path.parent))

    ordered = sorted(
        candidates,
        key=lambda item: (item.path.parts, item.include_container),
    )
    roots: list[_DiffTraversalRoot] = []
    for candidate in ordered:
        covering = next(
            (
                existing
                for existing in roots
                if candidate.path.parts[: len(existing.path.parts)]
                == existing.path.parts
            ),
            None,
        )
        if covering is None:
            roots.append(candidate)
        elif covering.path == candidate.path and candidate.include_container:
            roots[roots.index(covering)] = candidate
    return tuple(roots)


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
    command = ["hlsync"]
    if arguments.profile_prefix is not None:
        command.append(arguments.profile_prefix)
    command.extend(("diff", *arguments.pattern_operands))
    if arguments.pull:
        command.append("--pull")
    if arguments.prune_remote:
        command.append("--prune-remote")
    if arguments.recursive:
        command.append("--recursive")
    if arguments.included_only:
        command.append("-i")
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
        traverse_excluded=(
            include_excluded
            and arguments.prune_remote
            and _recursive_transfer_scope(arguments)
        ),
    )
    print("Reading remote files over FTPS...", file=progress, flush=True)
    remote = transport.snapshot(
        rules,
        selector,
        include_excluded=include_excluded,
        traverse_excluded=(
            include_excluded
            and arguments.prune_remote
            and _recursive_transfer_scope(arguments)
        ),
    )
    print("Comparing local and remote files...", file=progress, flush=True)
    plan = build_comparison(
        local,
        remote,
        direction=direction,
        prune_remote=arguments.prune_remote,
        selector=selector if arguments.pattern_operands else None,
    )
    untraversed_directories = frozenset(
        entry.path
        for entry in plan.entries
        if _comparison_entry_kind(entry, direction) == "directory"
        and not selector.may_match_descendant(entry.path)
        and entry.action != "excluded"
    )
    plan = mark_untraversed_directories(plan, untraversed_directories)
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
    color = _use_color(output)
    print(f"Checking differences for project '{name}'...", file=progress, flush=True)
    options = _active_options(arguments)
    if options is not None:
        print(options, file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    traversal_roots = _diff_traversal_roots(arguments, root)
    if resume is not None:
        root_index = next(
            (
                index
                for index, traversal_root in enumerate(traversal_roots)
                if resume.parts[: len(traversal_root.path.parts)]
                == traversal_root.path.parts
            ),
            None,
        )
        if root_index is None:
            raise SelectionError(f"resume directory '{resume}' is not reachable")
        traversal_roots = traversal_roots[root_index:]
    pending = [
        _PendingDiffDirectory(
            path=traversal_root.path,
            has_local=root.joinpath(*traversal_root.path.parts).is_dir(),
            has_remote=True,
            include_container=traversal_root.include_container,
            is_root=True,
            display_root=(
                traversal_root.path if len(traversal_roots) == 1 else None
            ),
            display_anchor=traversal_root.include_container,
        )
        for traversal_root in reversed(traversal_roots)
    ]
    seeking = resume is not None
    selected_count = 0
    displayed_count = 0
    with ExplicitFTPSTransport(project) as transport:
        if pending:
            for line in _scope_header_lines(
                pending[-1].display_root,
                anchored=pending[-1].display_anchor,
                color=color,
            ):
                print(line, file=output, flush=True)
        while pending:
            current = pending.pop()
            directory = current.path
            display_directory = directory.as_posix()
            local_listing = (
                list_local_directory(root, directory, rules)
                if current.has_local
                else TreeSnapshot()
            )
            remote_directory_exists = current.has_remote
            try:
                remote_listing = (
                    transport.list_directory(directory, rules)
                    if current.has_remote
                    else TreeSnapshot()
                )
            except PathOperationError:
                if not current.is_root or not directory.parts:
                    raise
                remote_directory_exists = False
                remote_listing = TreeSnapshot()
            descendants = _descendant_directories(
                local_listing,
                remote_listing,
                rules,
                selector,
                descend_remote_only=arguments.prune_remote,
                descend_excluded=(
                    arguments.prune_remote
                    and _recursive_transfer_scope(arguments)
                ),
            )
            pending_descendants = tuple(
                _PendingDiffDirectory(
                    path=path,
                    has_local=local_exists,
                    has_remote=remote_exists,
                    include_container=False,
                    is_root=False,
                    display_root=current.display_root,
                    display_anchor=current.display_anchor,
                )
                for path, local_exists, remote_exists in descendants
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
                    (
                        candidate
                        for candidate in pending_descendants
                        if candidate.path == branch
                    ),
                    None,
                )
                if matching_branch is None:
                    raise SelectionError(
                        f"resume directory '{resume}' is not reachable"
                    )
                later = tuple(
                    candidate
                    for candidate in pending_descendants
                    if candidate.path > branch
                )
                pending.extend(reversed(later))
                pending.append(matching_branch)
                continue

            seeking = False
            pending.extend(reversed(pending_descendants))
            local = _filtered_listing(
                local_listing,
                selector,
            )
            remote = _filtered_listing(
                remote_listing,
                selector,
            )
            if current.include_container and directory.parts:
                container_path = directory.as_posix()
                excluded = rules.excludes(container_path, is_directory=True)
                if current.has_local:
                    local = TreeSnapshot(
                        local.entries
                        + (
                            TreeEntry(
                                container_path,
                                "directory",
                                excluded=excluded,
                            ),
                        )
                    )
                if remote_directory_exists:
                    remote = TreeSnapshot(
                        remote.entries
                        + (
                            TreeEntry(
                                container_path,
                                "directory",
                                excluded=excluded,
                            ),
                        )
                    )
            selected_count += len(local.entries) + len(remote.entries)
            plan = build_comparison(
                local,
                remote,
                direction=direction,
                prune_remote=arguments.prune_remote,
            )
            descended_paths = frozenset(
                path.as_posix() for path, _, _ in descendants
            )
            collapsed_paths = frozenset(
                entry.path
                for entry in plan.entries
                if _comparison_entry_kind(entry, direction) == "directory"
                and entry.path not in descended_paths
                and entry.path != directory.as_posix()
                and entry.action != "excluded"
            )
            plan = mark_untraversed_directories(plan, collapsed_paths)
            shown = tuple(
                entry
                for entry in plan.entries
                if not arguments.included_only or entry.action != "excluded"
            )
            lines = _format_comparison_entries(
                shown,
                direction,
                color=color,
                collapsed_paths=collapsed_paths,
                display_path=lambda path: _scoped_display_path(
                    path,
                    display_root=current.display_root,
                ),
            )
            for line in lines:
                print(line, file=output, flush=True)
            displayed_count += len(lines)

            if arguments.paged:
                if not lines:
                    print(
                        f"  no entries in {display_directory}",
                        file=output,
                        flush=True,
                    )
                if pending:
                    print(
                        f"Resume: {_resume_command(arguments, pending[-1].path)}",
                        file=output,
                        flush=True,
                    )
                return

    if seeking:
        assert resume is not None
        raise SelectionError(f"resume directory '{resume}' is not reachable")
    if arguments.pattern_operands and selected_count == 0:
        raise SelectionError(f"file selector '{selector.pattern}' matched no paths")
    if displayed_count == 0:
        print("  no differences", file=output, flush=True)


def _format_transfer(name: str, result: TransferResult) -> str:
    direction = result.plan.direction.capitalize()
    if not result.succeeded:
        lines = [
            f"{direction} finished with errors for project '{name}': "
            f"{result.changed_count} completed, {result.failed_count} failed, "
            f"{result.skipped_count} skipped."
        ]
        lines.extend(
            f"  {issue.status:<7} {issue.path}: {issue.reason}"
            for issue in result.issues
        )
        return "\n".join(lines)
    count = result.changed_count
    if count == 0:
        nothing = f"  Nothing to {result.plan.direction}"
        if result.plan.direction == "push" and result.unchanged_file_count:
            files = result.unchanged_file_count
            noun = "file is" if files == 1 else "files are"
            nothing += f"; {files} {noun} up to date in this scope"
        lines = [f"{nothing}."]
    else:
        changes = f"{count} change{'s' if count != 1 else ''}"
        lines = [f"{direction} complete: {changes}."]
    skipped = [entry for entry in result.plan.entries if entry.action == "skip"]
    if result.plan.direction == "push":
        retained_remote = any(
            entry.action == "skip"
            or (entry.action == "excluded" and entry.remote_kind is not None)
            for entry in result.plan.entries
        )
        if retained_remote:
            lines.append("Remote-only paths retained; use -p to delete them.")
    else:
        if skipped:
            lines.append("Remote-only paths not restored:")
            lines.extend(f"  {entry.path}" for entry in skipped)
    return "\n".join(lines)


def _report_transfer_operation(
    operation: TransferOperation,
    progress: TextIO,
) -> None:
    labels = {
        "add": "Adding",
        "update": "Updating",
        "delete": "Deleting",
        "create": "Creating",
    }
    suffix = "/" if operation.kind == "directory" else ""
    print(
        f"  {labels[operation.action]:<8} {operation.path}{suffix}",
        file=progress,
        flush=True,
    )


def _transfer(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    progress: TextIO,
) -> tuple[str, TransferResult]:
    _, name, project = _resolve_project(arguments, store)
    root = _require_local_root(name, project)
    print(
        f"Preparing {arguments.command} for project '{name}'...",
        file=progress,
        flush=True,
    )
    options = _active_options(arguments)
    if options is not None:
        print(options, file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    with ExplicitFTPSTransport(project) as transport:
        if arguments.command == "push":
            print(
                "Checking for interrupted uploads...",
                file=progress,
                flush=True,
            )
            recoveries = transport.recover_artifacts(
                _file_selection(arguments, root)
            )
            for recovery in recoveries:
                print(f"  {recovery}", file=progress, flush=True)
        local, remote, plan = _build_plan(
            arguments,
            project,
            root,
            transport,
            direction=arguments.command,
            progress=progress,
            include_excluded=arguments.command == "push",
        )
        executable_actions = {
            "create-remote",
            "upload",
            "replace-remote",
            "replace-local",
            "delete-remote",
        }
        if any(entry.action in executable_actions for entry in plan.entries):
            progress_action = (
                "Pushing" if arguments.command == "push" else "Pulling"
            )
            print(f"{progress_action} changes...", file=progress, flush=True)
        result = execute_transfer(
            plan,
            local_root=root,
            local=local,
            remote=remote,
            transport=transport,
            progress=lambda operation: _report_transfer_operation(
                operation,
                progress,
            ),
        )
    return name, result


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
    try:
        raw_arguments, profile_prefix = _resolve_invocation(
            raw_arguments,
            stdin=stdin,
            stdout=stdout,
        )
    except ConfigurationError as error:
        parser.error(str(error))
    arguments = parser.parse_args(raw_arguments)
    arguments.profile_prefix = profile_prefix
    if arguments.legend:
        if arguments.command is not None:
            parser.error("--legend cannot be combined with a command")
        print(_format_legend(stdout), file=stdout)
        return 0
    if arguments.command is None:
        parser.error("a command is required unless --legend is supplied")
    configuration_store = store or ConfigurationStore()
    exit_status = 0
    try:
        _validate_profile_prefix(arguments)
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
            name, result = _transfer(arguments, configuration_store, stderr)
            message = _format_transfer(name, result)
            if not result.succeeded:
                exit_status = 1
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
        print(f"hlsync: error: {error}", file=stderr)
        return 1
    if message is not None:
        print(message, file=stdout)
    return exit_status


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)

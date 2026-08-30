from __future__ import annotations

import argparse
import os
import shlex
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TextIO, TypeVar

from hlsync import __version__
from hlsync.comparison import (
    ComparisonEntry,
    ComparisonPlan,
    build_comparison,
    mark_untraversed_directories,
)
from hlsync.config import (
    DEFAULT_PASSWORD_ENV,
    DEFAULT_USERNAME_ENV,
    ApplicationConfiguration,
    ConfigurationError,
    ConfigurationStore,
    GlobalRuleStore,
    ProfileConfiguration,
    RuleUpdate,
    canonical_local_root,
    validate_profile_name,
)
from hlsync.pattern_operands import (
    PatternOperandError,
    add_pattern_operands,
    normalize_pattern_operands,
)
from hlsync.rules import (
    RuleError,
    RuleSet,
    SyncRule,
    expand_path_operands,
    patterns_from_global_operands,
    patterns_from_operands,
    patterns_from_remote_operands,
)
from hlsync.selection import (
    DirectoryContentsSelection,
    FileSelection,
    FileSelector,
    FileSelectorSet,
    SelectionError,
)
from hlsync.snapshot import (
    SnapshotError,
    TreeEntry,
    TreeSnapshot,
    list_local_directory,
    snapshot_local,
)
from hlsync.transfer import (
    TransferError,
    TransferOperation,
    TransferResult,
    execute_transfer,
)
from hlsync.transport import ExplicitFTPSTransport, PathOperationError, TransportError

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


@dataclass(frozen=True)
class _PendingDiffOutput:
    lines: tuple[str, ...]


CANONICAL_COMMANDS = (
    "create",
    "connect",
    "map",
    "remove",
    "root",
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
COMMAND_ALIASES = {"ls": "list", "lsr": "list"}
PROFILE_AWARE_COMMANDS = frozenset(
    {
        "connect",
        "map",
        "remove",
        "root",
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
    if getattr(arguments, "remote", False):
        options.append("remote (--remote)")
    if getattr(arguments, "pull", False):
        options.append("pull perspective (--pull)")
    if getattr(arguments, "recursive", False):
        options.append("recursive (-r)")
    if getattr(arguments, "show_all", False):
        options.append("all entries (-a)")
    if getattr(arguments, "included_only", False):
        options.append("included paths only (-i)")
    if getattr(arguments, "keep_remote", False):
        options.append("keep remote-only paths (-k)")
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
        profile_name = validate_profile_name(first)
        raw_arguments = raw_arguments[1:]
        remote_list_alias = raw_arguments[0] == "lsr"
        raw_arguments[0] = _resolve_command_name(
            raw_arguments[0], stdin=stdin, stdout=stdout
        )
        if remote_list_alias:
            raw_arguments.insert(1, "--remote")
        return raw_arguments, profile_name
    remote_list_alias = first == "lsr"
    raw_arguments[0] = _resolve_command_name(first, stdin=stdin, stdout=stdout)
    if remote_list_alias:
        raw_arguments.insert(1, "--remote")
    return raw_arguments, None


def _validate_profile_prefix(arguments: argparse.Namespace) -> None:
    profile_name = getattr(arguments, "profile_prefix", None)
    if profile_name is not None and getattr(arguments, "global_rules", False):
        raise ConfigurationError("a profile prefix cannot be combined with --global")
    if profile_name is not None and arguments.command not in PROFILE_AWARE_COMMANDS:
        raise ConfigurationError(
            f"profile prefix '{profile_name}' cannot be used with "
            f"'{arguments.command}'"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hlsync",
        description=(
            "Transfer mapped files over explicit FTP over TLS. Run commands "
            "inside a mapped profile; prefix a command with a profile only for "
            "a one-command override. Commands may be shortened to any unique "
            "prefix."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--legend",
        action="store_true",
        help="show diff symbols and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser(
        "create",
        help="create an FTPS profile with a mapped local root",
        description=(
            "Create an FTPS profile using environment-variable credentials. "
            "Without --local-root, choose the current or another directory."
        ),
    )
    create_parser.add_argument("profile_name", help="new profile name")
    create_parser.add_argument("--host", required=True, help="FTPS server host")
    create_parser.add_argument(
        "--remote-root", required=True, help="absolute server directory"
    )
    create_parser.add_argument(
        "--protocol",
        choices=("ftps",),
        default="ftps",
        help="transfer protocol (default: ftps)",
    )
    create_parser.add_argument(
        "--port", type=int, default=21, help="server port (default: 21)"
    )
    create_parser.add_argument(
        "--username-env",
        help=f"username environment variable (default: {DEFAULT_USERNAME_ENV})",
    )
    create_parser.add_argument(
        "--password-env",
        help=f"password environment variable (default: {DEFAULT_PASSWORD_ENV})",
    )
    create_parser.add_argument(
        "--local-root",
        metavar="PATH",
        help=(
            "local profile directory; when omitted, offer the current "
            "directory and prompt for another if declined"
        ),
    )

    connect_parser = subparsers.add_parser(
        "connect",
        help="verify a profile's FTPS connection",
        usage="hlsync connect [PROFILE]\n       hlsync PROFILE connect",
        description=(
            "Check secure FTPS connectivity, then disconnect. Infer the profile "
            "from the current directory unless named."
        ),
    )
    connect_parser.add_argument(
        "profile_name", nargs="?", help="profile; inferred when omitted"
    )

    map_parser = subparsers.add_parser(
        "map",
        help="change a profile's local or remote root",
        usage=(
            "hlsync map [PROFILE] [--local-root PATH] [--remote-root PATH]\n"
            "       hlsync PROFILE map [--local-root PATH] [--remote-root PATH]"
        ),
        description=(
            "Change mapped roots after a [y/N] confirmation. Omitted roots stay "
            "unchanged; with neither option, use the current local directory."
        ),
    )
    map_parser.add_argument(
        "profile_name", nargs="?", help="profile; inferred when omitted"
    )
    map_parser.add_argument(
        "--local-root",
        metavar="PATH",
        help="new local root; defaults to the current directory",
    )
    map_parser.add_argument(
        "--remote-root",
        metavar="PATH",
        help="new absolute remote root; omitted leaves it unchanged",
    )

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
                f"       hlsync [PROFILE] {command} --pattern PATTERN ...\n"
                f"       hlsync [PROFILE] {command} --remote PATH ...\n"
                f"       hlsync {command} -g [PATTERN ...]"
            ),
            description=(
                f"Record or, with no paths, list {rule_name} rules. Paths "
                "resolve locally; --pattern matches future paths, --remote "
                "protects remote paths, and -g applies globally."
            ),
        )
        add_pattern_operands(
            rules_parser,
            required=False,
            metavar="PATH",
            help_text=(
                "paths, wildcard expressions, or comma-separated groups; "
                f"omit to list {rule_name} rules; with -g, operands are "
                "reusable profile-root patterns"
            ),
        )
        rules_parser.add_argument(
            "--remote",
            action="store_true",
            help="apply rules to remote paths that must be left untouched",
        )
        rules_parser.add_argument(
            "--pattern",
            action="store_true",
            help="record operands as reusable wildcard patterns",
        )
        rules_parser.add_argument(
            "-g",
            "--global",
            dest="global_rules",
            action="store_true",
            help="manage rules shared by every profile",
        )

    rules_parser = subparsers.add_parser(
        "rules",
        help="list or remove synchronization rules",
        usage=(
            "hlsync [PROFILE] rules\n"
            "       hlsync [PROFILE] rules remove RULE_ID\n"
            "       hlsync rules -g [remove GLOBAL_RULE_ID]"
        ),
        description=(
            "List synchronization rules, or remove one by its displayed ID. "
            "Profile IDs are numeric; global IDs use the gN form."
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
        metavar="RULE_ID",
        help="displayed rule ID required by remove",
    )
    rules_parser.add_argument(
        "-g",
        "--global",
        dest="global_rules",
        action="store_true",
        help="show or remove rules shared by every profile",
    )
    remove_parser = subparsers.add_parser(
        "remove",
        help="remove a profile",
        usage="hlsync remove [PROFILE]\n       hlsync PROFILE remove",
        description=(
            "Remove local profile configuration only; remote files stay "
            "unchanged. Infer the profile when omitted."
        ),
    )
    remove_parser.add_argument(
        "profile_name", nargs="?", help="profile; inferred when omitted"
    )

    root_parser = subparsers.add_parser(
        "root",
        help="print a profile's mapped local root",
        usage="hlsync root [PROFILE]\n       hlsync PROFILE root",
        description=(
            "Print only the canonical local root, suitable for "
            "cd \"$(hlsync root PROFILE)\"."
        ),
    )
    root_parser.add_argument(
        "profile_name",
        nargs="?",
        metavar="PROFILE",
        help="profile name; inferred from the current directory when omitted",
    )

    profile_parser = subparsers.add_parser(
        "profile",
        help="show the current profile or detailed profile information",
        usage=(
            "hlsync profile [PROFILE] [--details]\n"
            "       hlsync PROFILE profile [--details]"
        ),
        description=(
            "Print the inferred or named profile. --details adds its "
            "connection, mapping, credentials, and rules."
        ),
    )
    profile_parser.add_argument(
        "profile_name",
        nargs="?",
        metavar="PROFILE",
        help="profile name; inferred from the current directory when omitted",
    )
    profile_parser.add_argument(
        "--details",
        dest="profile_details",
        action="store_true",
        help="show endpoint, mapping, credentials, and rule count",
    )

    subparsers.add_parser(
        "profiles",
        help="list configured profiles",
        description="List profiles; * marks the one containing this directory.",
    )

    list_parser = subparsers.add_parser(
        "list",
        aliases=("lsr",),
        help="list the current local or remote directory",
        usage=(
            "hlsync [PROFILE] list [--remote] [-r] [-i] [PATH ...]\n"
            "       hlsync [PROFILE] lsr [-r] [-i] [PATH ...]"
        ),
        description=(
            "With no PATH, list the current directory one level. A directory "
            "PATH is also shallow unless -r. Use --remote/lsr for remote and "
            "-i to hide exclusions."
        ),
    )
    add_pattern_operands(
        list_parser,
        required=False,
        metavar="PATH",
        help_text=(
            "relative paths or wildcards; default: current directory"
        ),
    )
    list_parser.add_argument(
        "--remote",
        action="store_true",
        help="list the mapped remote directory over FTPS",
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
            "       [--pull | --keep-remote] [-r] [-a] [-i] [--paged]\n"
            "       [--resume DIRECTORY]"
        ),
        description=(
            "With no PATH, preview the current directory one level. A directory "
            "PATH is also shallow unless -r. Use --pull to reverse direction, "
            "-i to hide exclusions, and -a to show everything."
        ),
    )
    add_pattern_operands(
        diff_parser,
        required=False,
        metavar="PATH",
        help_text=(
            "relative paths or wildcards; default: current directory"
        ),
    )
    diff_direction = diff_parser.add_mutually_exclusive_group()
    diff_direction.add_argument(
        "--pull",
        action="store_true",
        help="show changes from the remote perspective without remote deletion",
    )
    diff_parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="include descendants of selected directories",
    )
    _add_included_only_argument(diff_parser)
    diff_parser.add_argument(
        "-a",
        "--all",
        dest="show_all",
        action="store_true",
        help="also show unchanged and untraversed paths",
    )
    diff_parser.add_argument(
        "--paged",
        action="store_true",
        help="show one directory, then exit with a resume command",
    )
    diff_parser.add_argument(
        "--resume",
        metavar="DIRECTORY",
        help="resume a paged diff at a profile-relative directory",
    )
    diff_direction.add_argument(
        "-k",
        "--keep-remote",
        action="store_true",
        help="show remote-only paths as retained instead of deleted",
    )
    transfer_help = {
        "push": "upload local changes to the remote profile",
        "pull": "replace changed local files from the remote profile",
    }
    transfer_description = {
        "push": (
            "Push local changes. With no PATH, push the current subtree "
            "recursively. A directory PATH is shallow unless -r. Remote-only "
            "directory PATHs are deleted recursively unless -k."
        ),
        "pull": (
            "Pull requires a PATH. A directory PATH is shallow unless -r; "
            "missing local paths stay missing."
        ),
    }
    for command in ("push", "pull"):
        transfer_parser = subparsers.add_parser(
            command,
            help=transfer_help[command],
            description=transfer_description[command],
            usage=(
                (
                    "hlsync [PROFILE] pull PATH [PATH ...] [-r]"
                    if command == "pull"
                    else "hlsync [PROFILE] push [PATH ...] [-r]"
                )
                + (" [-k]" if command == "push" else "")
            ),
        )
        add_pattern_operands(
            transfer_parser,
            required=command == "pull",
            metavar="PATH",
            help_text=(
                "relative paths or wildcards; default: current subtree"
                if command == "push"
                else "relative paths or wildcards"
            ),
        )
        transfer_parser.add_argument(
            "-r",
            "--recursive",
            action="store_true",
            help=(
                "recurse into selected directories (implied with no PATH)"
                if command == "push"
                else "recurse into selected directories"
            ),
        )
        if command == "push":
            transfer_parser.add_argument(
                "-k",
                "--keep-remote",
                action="store_true",
                help="retain selected remote-only paths",
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


def _create_profile(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    stdin: TextIO,
    stdout: TextIO,
) -> str:
    name = validate_profile_name(arguments.profile_name)
    configuration = store.load()
    if name in configuration.profiles:
        raise ConfigurationError(f"profile '{name}' already exists")
    profile = ProfileConfiguration(
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
    configuration.profiles[name] = profile
    if arguments.local_root is not None:
        local_root = canonical_local_root(arguments.local_root)
    else:
        current_root = canonical_local_root(Path.cwd())
        prompt = (
            f"Map current directory '{current_root}' to "
            f"'{name}:{profile.remote_root}'? [Y/n] "
        )
        if _confirm(prompt, stdin, stdout, default=True):
            local_root = current_root
        else:
            print(
                "What local folder should be mapped instead? ",
                end="",
                file=stdout,
                flush=True,
            )
            supplied_root = stdin.readline()
            if supplied_root == "" or not supplied_root.strip():
                raise ConfigurationError("a local folder is required")
            local_root = canonical_local_root(supplied_root.strip())
    configuration.set_profile_roots(
        name,
        local_root=local_root,
        remote_root=profile.remote_root,
    )
    message = (
        f"Created FTPS profile '{name}'.\n"
        f"Mapped '{local_root}' to '{name}:{profile.remote_root}'."
    )
    _global_rule_store(store).load()
    store.save(configuration)
    return message


def _global_rule_store(store: ConfigurationStore) -> GlobalRuleStore:
    return GlobalRuleStore(store.path.with_name("rules.json"))


def _effective_rules(
    store: ConfigurationStore,
    profile: ProfileConfiguration,
) -> RuleSet:
    global_rules = _global_rule_store(store).load().rules
    return RuleSet.layered(global_rules, profile.rules)


def _resolve_profile(
    arguments: argparse.Namespace, store: ConfigurationStore
) -> tuple[ApplicationConfiguration, str, ProfileConfiguration]:
    configuration = store.load()
    prefix_name = getattr(arguments, "profile_prefix", None)
    positional_name = getattr(arguments, "profile_name", None)
    if prefix_name is not None and positional_name is not None:
        raise ConfigurationError(
            "profile was specified both before the command and as an argument"
        )
    supplied_name = prefix_name or positional_name
    if supplied_name is None:
        active = configuration.profile_for_path(Path.cwd().resolve(strict=True))
        if active is None:
            raise ConfigurationError(
                "current directory is not inside a mapped profile; prefix the "
                "command with a profile (hlsync PROFILE COMMAND)"
            )
        name, profile = active
        return configuration, name, profile
    name = validate_profile_name(supplied_name)
    if name not in configuration.profiles:
        raise ConfigurationError(f"profile '{name}' does not exist")
    return configuration, name, configuration.profiles[name]


def _effective_current_directory(
    arguments: argparse.Namespace,
    profile_root: Path,
) -> Path:
    if getattr(arguments, "profile_prefix", None) is not None:
        return profile_root.resolve(strict=True)
    return Path.cwd().resolve(strict=True)


def _connect(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    _, name, profile = _resolve_profile(arguments, store)
    with ExplicitFTPSTransport(profile):
        pass
    return f"Verified secure connectivity to profile '{name}'."


def _map(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    stdin: TextIO,
    stdout: TextIO,
) -> str:
    configuration, name, profile = _resolve_profile(arguments, store)
    if arguments.local_root is not None:
        local_root = canonical_local_root(arguments.local_root)
    elif arguments.remote_root is None or profile.local_root is None:
        local_root = canonical_local_root(Path.cwd())
    else:
        local_root = profile.local_root
    remote_root = (
        arguments.remote_root
        if arguments.remote_root is not None
        else profile.remote_root
    )
    candidate = profile.with_roots(
        local_root=local_root,
        remote_root=remote_root,
    )
    changes = []
    if profile.local_root != candidate.local_root:
        changes.append(
            f"  Local root: {profile.local_root or 'not mapped'} "
            f"→ {candidate.local_root}"
        )
    if profile.remote_root != candidate.remote_root:
        changes.append(
            f"  Remote root: {profile.remote_root} → {candidate.remote_root}"
        )
    if not changes:
        return f"Profile '{name}' mapping is unchanged."

    configuration.set_profile_roots(
        name,
        local_root=candidate.local_root,
        remote_root=candidate.remote_root,
    )
    prompt = "\n".join(
        (f"Change mapping for profile '{name}'?", *changes, "Continue? [y/N] ")
    )
    if not _confirm(prompt, stdin, stdout, default=False):
        return f"Kept profile '{name}' mapping unchanged."
    store.save(configuration)
    return "\n".join((f"Updated profile '{name}' mapping:", *changes))


def _format_rules(
    name: str,
    rules: tuple[SyncRule, ...],
    *,
    heading: str,
    grouped: bool = False,
    global_scope: bool = False,
    show_targets: bool = False,
) -> str:
    scope_heading = (
        f"Global {heading.lower()}"
        if global_scope
        else f"{heading} for profile '{name}'"
    )
    if not rules:
        return f"No {scope_heading.lower()}."
    identifiers = {
        rule.id: _format_rule_id(rule, global_scope=global_scope) for rule in rules
    }
    width = max(len(identifier) for identifier in identifiers.values())
    if grouped:
        target_groups = (
            (("Local", tuple(rule for rule in rules if rule.target == "local")),
             ("Remote", tuple(rule for rule in rules if rule.target == "remote")))
            if show_targets
            else (("", rules),)
        )
        lines = [f"{scope_heading}:"]
        for target_heading, target_rules in target_groups:
            if not target_rules:
                continue
            if target_heading:
                lines.extend(("", target_heading))
            groups: dict[str, list[tuple[SyncRule, str]]] = {}
            for rule in target_rules:
                group, expression = _rule_display_location(rule)
                groups.setdefault(group, []).append((rule, expression))
            for group in sorted(groups, key=_rule_group_key):
                lines.extend(("", group))
                for rule, expression in sorted(
                    groups[group],
                    key=lambda item: (item[1].casefold(), item[1], item[0].id),
                ):
                    lines.append(
                        f"  {identifiers[rule.id]:>{width}}  "
                        f"{rule.action:<7} {expression}"
                    )
        if _rules_need_precedence_note(rules):
            lines.extend(("", "Higher rule IDs take precedence when rules overlap."))
        return "\n".join(lines)
    return "\n".join(
        (
            f"{scope_heading}:",
            *(
                f"  {identifiers[rule.id]:>{width}}  {rule.action:<7} "
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
    return any(
        len({rule.action for rule in rules if rule.target == target}) > 1
        for target in ("local", "remote")
    )


def _format_rule_expression(rule: SyncRule) -> str:
    return rule.pattern if "*" in rule.pattern else f"./{rule.pattern}"


def _format_rule_id(rule: SyncRule, *, global_scope: bool) -> str:
    return f"g{rule.id}" if global_scope else str(rule.id)


def _parse_rule_id(value: str, *, global_scope: bool) -> int:
    identifier = value[1:] if global_scope and value.startswith("g") else value
    valid_prefix = not global_scope or value.startswith("g")
    if not valid_prefix or not identifier.isdigit() or int(identifier) < 1:
        expected = "g-prefixed (for example g3)" if global_scope else "numeric"
        raise ConfigurationError(f"rule id must be {expected} in this scope")
    return int(identifier)


def _change_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    *,
    include: bool,
) -> str:
    patterns = normalize_pattern_operands(arguments)
    target = "remote" if arguments.remote else "local"
    if not patterns:
        if arguments.pattern:
            raise ConfigurationError("--pattern requires at least one operand")
        action = "include" if include else "exclude"
        kind = "Inclusion" if include else "Exclusion"
        if arguments.remote:
            kind = f"Remote {kind.lower()}"
        if arguments.global_rules:
            rules = tuple(
                rule
                for rule in _global_rule_store(store).load().rules
                if rule.action == action and rule.target == target
            )
            return _format_rules(
                "",
                rules,
                heading=f"{kind} rules",
                grouped=True,
                global_scope=True,
            )
        _, name, profile = _resolve_profile(arguments, store)
        rules = tuple(
            rule
            for rule in profile.rules
            if rule.action == action and rule.target == target
        )
        return _format_rules(name, rules, heading=f"{kind} rules", grouped=True)
    if arguments.global_rules:
        global_store = _global_rule_store(store)
        configuration = global_store.load()
        normalized = patterns_from_global_operands(
            patterns,
            trailing_slash_tree=not arguments.remote,
        )
        configuration, update = configuration.with_appended_rules(
            "include" if include else "exclude",
            normalized,
            target=target,
        )
        global_store.save(configuration)
        return _format_rule_update(
            "",
            update,
            include=include,
            global_scope=True,
            target=target,
        )
    configuration, name, profile = _resolve_profile(arguments, store)
    root = _require_local_root(name, profile)
    current_directory = _effective_current_directory(arguments, root)
    operands = (
        patterns
        if arguments.pattern or arguments.remote
        else expand_path_operands(
            patterns,
            profile_root=root,
            current_directory=current_directory,
        )
    )
    normalizer = (
        patterns_from_remote_operands
        if arguments.remote
        else patterns_from_operands
    )
    normalized = normalizer(
        operands, profile_root=root, current_directory=current_directory
    )
    update = configuration.append_rules(
        name,
        "include" if include else "exclude",
        normalized,
        target=target,
        base_rules=_global_rule_store(store).load().rules,
    )
    store.save(configuration)
    return _format_rule_update(name, update, include=include, target=target)


def _format_rule_update(
    name: str,
    update: RuleUpdate,
    *,
    include: bool,
    global_scope: bool = False,
    target: str = "local",
) -> str:
    scope = "global synchronization policy" if global_scope else f"profile '{name}'"
    if update.added and update.removed:
        lines = [f"Updated synchronization rules for {scope}:"]
        lines.extend(
            f"  added    {_format_rule_id(rule, global_scope=global_scope)}  "
            f"{rule.action:<7} {_format_rule_expression(rule)}"
            for rule in update.added
        )
        lines.extend(
            f"  removed  {_format_rule_id(rule, global_scope=global_scope)}  "
            f"{rule.action:<7} {_format_rule_expression(rule)}"
            for rule in update.removed
        )
        return "\n".join(lines)
    if update.added:
        action = "Inclusion" if include else "Exclusion"
        if target == "remote":
            action = f"Remote {action.lower()}"
        if global_scope:
            identifiers = tuple(
                _format_rule_id(rule, global_scope=True) for rule in update.added
            )
            width = max(len(identifier) for identifier in identifiers)
            return "\n".join(
                (
                    f"Recorded global {action.lower()} rules:",
                    *(
                        f"  {identifier:>{width}}  {rule.action:<7} "
                        f"{_format_rule_expression(rule)}"
                        for rule, identifier in zip(
                            update.added, identifiers, strict=True
                        )
                    ),
                )
            )
        return _format_rules(
            name,
            update.added,
            heading=f"Recorded {action.lower()} rules",
        )
    if update.removed:
        result = "included" if include else "excluded"
        if target == "remote":
            result = f"remotely {result}"
        remaining_scope = (
            "global synchronization policy"
            if global_scope
            else f"policy for profile '{name}'"
        )
        lines = [
            f"Paths are {result} by the remaining {remaining_scope};",
            "removed the unnecessary rules:",
        ]
        identifiers = tuple(
            _format_rule_id(rule, global_scope=global_scope)
            for rule in update.removed
        )
        width = max(len(identifier) for identifier in identifiers)
        lines.extend(
            f"  {identifier:>{width}}  {rule.action:<7} "
            f"{_format_rule_expression(rule)}"
            for rule, identifier in zip(update.removed, identifiers, strict=True)
        )
        return "\n".join(lines)
    return f"Synchronization rules for {scope} are unchanged."


def _manage_rules(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    if arguments.global_rules:
        global_store = _global_rule_store(store)
        global_configuration = global_store.load()
        if arguments.operation is None:
            if arguments.rule_id is not None:
                raise ConfigurationError("a rule id requires the remove operation")
            return _format_rules(
                "",
                global_configuration.rules,
                heading="Synchronization rules",
                grouped=True,
                global_scope=True,
                show_targets=True,
            )
        if arguments.rule_id is None:
            raise ConfigurationError("rules remove requires a rule id")
        global_configuration, removed = global_configuration.without_rule(
            _parse_rule_id(arguments.rule_id, global_scope=True)
        )
        global_store.save(global_configuration)
        return (
            f"Removed global rule {_format_rule_id(removed, global_scope=True)}: "
            f"{removed.action} {_format_rule_expression(removed)}"
        )
    configuration, name, profile = _resolve_profile(arguments, store)
    if arguments.operation is None:
        if arguments.rule_id is not None:
            raise ConfigurationError("a rule id requires the remove operation")
        global_rules = _format_rules(
            "",
            _global_rule_store(store).load().rules,
            heading="Synchronization rules",
            grouped=True,
            global_scope=True,
            show_targets=True,
        )
        profile_rules = _format_rules(
            name,
            profile.rules,
            heading="Synchronization rules",
            grouped=True,
            show_targets=True,
        )
        return (
            f"{global_rules}\n\n{profile_rules}\n\n"
            "Global rules apply first; profile rules override them."
        )
    if arguments.rule_id is None:
        raise ConfigurationError("rules remove requires a rule id")
    removed = configuration.remove_rule(
        name,
        _parse_rule_id(arguments.rule_id, global_scope=False),
    )
    store.save(configuration)
    return (
        f"Removed rule {removed.id} from profile '{name}': "
        f"{removed.action} {_format_rule_expression(removed)}"
    )


def _remove(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    configuration, name, _ = _resolve_profile(arguments, store)
    del configuration.profiles[name]
    store.save(configuration)
    return f"Removed profile '{name}'."


def _list_profiles(store: ConfigurationStore) -> str:
    configuration = store.load()
    if not configuration.profiles:
        return "No profiles configured."

    active = configuration.profile_for_path(Path.cwd().resolve(strict=True))
    active_name = active[0] if active is not None else None
    return "\n".join(
        f"{'*' if name == active_name else ' '} {name}"
        for name in sorted(configuration.profiles)
    )


def _show_profile(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    implicit = (
        getattr(arguments, "profile_prefix", None) is None
        and arguments.profile_name is None
    )
    if implicit:
        configuration = store.load()
        active = configuration.profile_for_path(Path.cwd().resolve(strict=True))
        if active is None:
            return "No active profile. Use hlsync PROFILE COMMAND."
        name, profile = active
    else:
        _, name, profile = _resolve_profile(arguments, store)
    if not arguments.profile_details:
        return name
    return "\n".join(
        (
            f"Profile '{name}':",
            f"  Protocol: {profile.type.upper()}",
            f"  Host: {profile.host}:{profile.port}",
            f"  Remote root: {profile.remote_root}",
            f"  Local root: {profile.local_root or 'not mapped'}",
            f"  Username env: {profile.username_env}",
            f"  Password env: {profile.password_env}",
            f"  Rules: {len(profile.rules)}",
        )
    )


def _show_root(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    _, name, profile = _resolve_profile(arguments, store)
    return os.fspath(_require_local_root(name, profile))


def _require_local_root(name: str, profile: ProfileConfiguration) -> Path:
    if profile.local_root is None:
        raise ConfigurationError(f"profile '{name}' has not been mapped")
    return Path(profile.local_root)


def _format_tree_listing(
    arguments: argparse.Namespace,
    snapshot: TreeSnapshot,
    *,
    heading: str,
    empty_message: str,
    display_base: PurePosixPath,
    output: TextIO,
    status_for: Callable[
        [TreeEntry], tuple[str, str | None, bool, str | None]
    ],
) -> str:
    if not snapshot.entries:
        return empty_message
    lines = [heading]
    options = _active_options(arguments)
    if options is not None:
        lines.append(options)
    color = _use_color(output)
    emitted_directories: set[str] = set()
    for entry in _file_browser_order(
        snapshot.entries,
        path_of=lambda item: item.path,
        directory_of=lambda item: item.kind == "directory",
    ):
        profile_path = PurePosixPath(entry.path)
        try:
            relative = profile_path.relative_to(display_base)
        except ValueError as error:
            raise SelectionError(
                f"selected path '{entry.path}' is outside the display scope"
            ) from error
        for index, part in enumerate(relative.parts[:-1]):
            ancestor = display_base / PurePosixPath(*relative.parts[: index + 1])
            ancestor_path = ancestor.as_posix()
            if ancestor_path in emitted_directories:
                continue
            lines.append(
                _format_path_line(
                    " ",
                    directory=True,
                    path=part,
                    depth=index,
                    color=color,
                    marker_color=None,
                    excluded=False,
                )
            )
            emitted_directories.add(ancestor_path)
        marker, marker_color, excluded, path_color = status_for(entry)
        lines.append(
            _format_path_line(
                marker,
                directory=entry.kind == "directory",
                path=relative.name,
                depth=max(len(relative.parts) - 1, 0),
                color=color,
                marker_color=marker_color,
                excluded=excluded,
                path_color=path_color,
            )
        )
        if entry.kind == "directory":
            emitted_directories.add(entry.path)
    return "\n".join(lines)


def _list_local(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    output: TextIO,
) -> str:
    _, name, profile = _resolve_profile(arguments, store)
    root = _require_local_root(name, profile)
    selector = _list_selection(arguments, root)
    raw_snapshot = snapshot_local(
        root,
        _effective_rules(store, profile),
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
    display_base = _profile_relative_current_directory(arguments, root)
    return _format_tree_listing(
        arguments,
        snapshot,
        heading=f"Local tree for profile '{name}':",
        empty_message=f"Local tree for profile '{name}' is empty.",
        display_base=display_base,
        output=output,
        status_for=lambda entry: (
            "x" if entry.excluded else " ",
            "\033[90m" if entry.excluded else None,
            entry.excluded,
            None,
        ),
    )


def _list_remote(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
    progress: TextIO,
    output: TextIO,
) -> str:
    _, name, profile = _resolve_profile(arguments, store)
    root = _require_local_root(name, profile)
    selector = _list_selection(arguments, root)
    rules = _effective_rules(store, profile)
    print(f"Listing remote files for profile '{name}'...", file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    with ExplicitFTPSTransport(profile) as transport:
        raw_snapshot = transport.snapshot(
            rules,
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
            and (
                not arguments.included_only
                or (not entry.excluded and not entry.remote_excluded)
            )
        )
    )
    display_base = _profile_relative_current_directory(arguments, root)

    def remote_status(
        entry: TreeEntry,
    ) -> tuple[str, str | None, bool, str | None]:
        if entry.remote_excluded:
            return (
                "r x",
                _DIFF_MARKER_COLORS["x"],
                True,
                (
                    _EXCLUDED_DIRECTORY_COLOR
                    if entry.kind == "directory"
                    else _DIFF_MARKER_COLORS["x"]
                ),
            )
        if entry.excluded:
            return "r !", _EXCLUDED_REMOTE_COLOR, True, _EXCLUDED_REMOTE_COLOR
        return " ", None, False, None

    return _format_tree_listing(
        arguments,
        snapshot,
        heading=f"Remote tree for profile '{name}':",
        empty_message=f"Remote tree for profile '{name}' is empty.",
        display_base=display_base,
        output=output,
        status_for=remote_status,
    )


def _comparison_kind(entry: ComparisonEntry) -> str:
    if (
        entry.local_kind is not None
        and entry.remote_kind is not None
        and entry.local_kind != entry.remote_kind
    ):
        return f"{entry.local_kind}->{entry.remote_kind}"
    return entry.local_kind or entry.remote_kind or "unknown"


def _comparison_marker(entry: ComparisonEntry, direction: str) -> str:
    if entry.state == "remote-excluded":
        return "r x"
    if entry.action == "excluded":
        return "r !" if entry.remote_kind is not None else "l x"
    if entry.action == "conflict":
        return "  ?"
    if entry.action == "unchanged":
        return "  ="
    if entry.action == "untraversed":
        return "r  " if entry.state == "remote-only" else "   "
    if entry.action == "skip":
        return "r  " if entry.state == "remote-only" else "l  "
    if entry.state == "changed":
        return "  ~"
    if direction == "push":
        return "l +" if entry.state == "local-only" else "r -"
    return "r +" if entry.state == "remote-only" else "l -"


def _comparison_marker_color(marker: str) -> str | None:
    action = marker[-1]
    if marker == "r x":
        return _DIFF_MARKER_COLORS["x"]
    return _DIFF_MARKER_COLORS.get(action) or _DIFF_MARKER_COLORS.get(marker.strip())


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
        ("l +", "local-only; upload", _DIFF_MARKER_COLORS["+"]),
        ("  ~", "present on both sides; update", _DIFF_MARKER_COLORS["~"]),
        ("r -", "remote-only; delete", _DIFF_MARKER_COLORS["-"]),
        ("r  ", "remote-only; retain", _DIFF_MARKER_COLORS["r"]),
        ("r x", "remote-excluded; leave untouched", _EXCLUDED_REMOTE_COLOR),
        ("?", "conflict", _DIFF_MARKER_COLORS["?"]),
        ("=", "unchanged file", None),
        ("l x", "local-excluded, absent remotely", _DIFF_MARKER_COLORS["x"]),
        ("r !", "local-excluded, present remotely", _DIFF_MARKER_COLORS["!"]),
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
    omit_marker = omit_empty_directory_marker and directory and not marker.strip()
    body = (
        f"{label}{traversal}"
        if omit_marker
        else f"{marker} {label}{traversal}"
    )
    line = f"{indent}{body}"
    if not color:
        return line
    if omit_marker:
        directory_color = (
            _COLLAPSED_DIRECTORY_COLOR
            if collapsed
            else path_color
            or (_EXCLUDED_DIRECTORY_COLOR if excluded else _DIRECTORY_COLOR)
        )
        suffix = " ▸" if collapsed else ""
        return f"{indent}{directory_color}{path}/{suffix}{_RESET}"
    if len(marker) == 3:
        side, action = marker[0], marker[2]
        side_color = _DIFF_MARKER_COLORS.get(side)
        rendered_side = (
            f"{side_color}{side}{_RESET}" if side_color and side != " " else side
        )
        rendered_action = (
            f"{marker_color}{action}{_RESET}"
            if marker_color and action != " "
            else action
        )
        rendered_status = f"{rendered_side} {rendered_action}"
        if directory:
            directory_color = path_color or (
                _EXCLUDED_DIRECTORY_COLOR if excluded else _DIRECTORY_COLOR
            )
            suffix = " ▸" if collapsed else ""
            return (
                f"{indent}{rendered_status} "
                f"{directory_color}{path}/{suffix}{_RESET}"
            )
        path_style = marker_color or side_color
        rendered_path = (
            f"{path_style}{label}{traversal}{_RESET}"
            if path_style
            else f"{label}{traversal}"
        )
        return f"{indent}{rendered_status} {rendered_path}"
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
    for entry in entries:
        parts = PurePosixPath(path_of(entry)).parts
        directory_paths.update(
            PurePosixPath(*parts[:index]).as_posix()
            for index in range(1, len(parts))
        )

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
            "   "
            if directory and entry.action == "unchanged"
            else _comparison_marker(entry, direction)
        )
        remote_exclusion_color = (
            (
                (
                    _EXCLUDED_DIRECTORY_COLOR
                    if directory
                    else _DIFF_MARKER_COLORS["x"]
                )
                if entry.state == "remote-excluded"
                else _EXCLUDED_REMOTE_COLOR
            )
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
                marker_color=_comparison_marker_color(marker),
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
    profile_path = PurePosixPath(path)
    if display_root is None:
        return 0, profile_path.as_posix()
    if profile_path == display_root and display_root.parts:
        return 0, display_root.as_posix()
    relative = (
        profile_path.relative_to(display_root)
        if display_root.parts
        else profile_path
    )
    depth = len(relative.parts) if display_root.parts else max(
        len(relative.parts) - 1,
        0,
    )
    return depth, relative.name


def _comparison_ancestors(
    path: str,
    *,
    display_root: PurePosixPath | None,
) -> tuple[PurePosixPath, ...]:
    profile_path = PurePosixPath(path)
    start = len(display_root.parts) if display_root is not None else 1
    start = max(start, 1)
    return tuple(
        PurePosixPath(*profile_path.parts[:length])
        for length in range(start, len(profile_path.parts))
        if display_root is None
        or profile_path.parts[: len(display_root.parts)] == display_root.parts
    )


def _format_compact_comparison_entry(
    entry: ComparisonEntry,
    direction: str,
    *,
    color: bool,
    collapsed: bool,
    display_root: PurePosixPath | None,
    emitted_directories: set[str],
) -> tuple[str, ...]:
    lines: list[str] = []
    for ancestor in _comparison_ancestors(
        entry.path,
        display_root=display_root,
    ):
        ancestor_path = ancestor.as_posix()
        if ancestor_path in emitted_directories:
            continue
        depth, label = _scoped_display_path(
            ancestor_path,
            display_root=display_root,
        )
        lines.append(
            _format_path_line(
                " ",
                directory=True,
                path=label,
                depth=depth,
                color=color,
                marker_color=None,
                excluded=False,
                omit_empty_directory_marker=True,
            )
        )
        emitted_directories.add(ancestor_path)
    lines.extend(
        _format_comparison_entries(
            (entry,),
            direction,
            color=color,
            collapsed_paths=frozenset((entry.path,)) if collapsed else frozenset(),
            display_path=lambda path: _scoped_display_path(
                path,
                display_root=display_root,
            ),
        )
    )
    if _comparison_entry_kind(entry, direction) == "directory":
        emitted_directories.add(entry.path)
    return tuple(lines)


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


def _leaf_selectors(selection: FileSelection) -> tuple[FileSelector, ...]:
    if isinstance(selection, FileSelector):
        return (selection,)
    if isinstance(selection, FileSelectorSet):
        return selection.selectors
    return _leaf_selectors(selection.traversal)


def _remote_push_selection(
    arguments: argparse.Namespace,
    root: Path,
    local: TreeSnapshot,
    selection: FileSelection,
) -> FileSelection:
    """Fully inspect explicit paths that are absent from local authority."""
    current_directory = _effective_current_directory(arguments, root)
    local_entries = {entry.path: entry for entry in local.entries}
    recursive_roots: list[FileSelector] = []
    for operand in normalize_pattern_operands(arguments):
        if operand == "." or any(character in operand for character in "*?["):
            continue
        selected = FileSelector.from_argument(
            operand.rstrip("/"),
            profile_root=root,
            current_directory=current_directory,
        )
        local_entry = local_entries.get(selected.pattern)
        if local_entry is None or (
            local_entry.excluded and local_entry.kind == "directory"
        ):
            recursive_roots.append(FileSelector(f"{selected.pattern}/**"))
    if not recursive_roots:
        return selection
    return FileSelectorSet((*_leaf_selectors(selection), *recursive_roots))


def _selection_from_values(
    values: Sequence[str],
    root: Path,
    current_directory: Path,
) -> FileSelection:
    selectors = tuple(
        FileSelector.from_argument(
            value,
            profile_root=root,
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
    descendants: list[tuple[PurePosixPath, bool, bool]] = []
    for path in paths:
        local_entry = local_directories.get(path)
        remote_entry = remote_directories.get(path)
        if local_entry is None and not descend_remote_only:
            continue
        if selector is not None and not selector.may_match_descendant(path):
            continue
        if (
            local_entry is not None
            and local_entry.excluded
            and not rules.may_include_descendant(path, target="local")
            and not descend_excluded
        ):
            continue
        if any(
            entry is not None and entry.remote_excluded
            for entry in (local_entry, remote_entry)
        ):
            continue
        descendants.append(
            (PurePosixPath(path), local_entry is not None, remote_entry is not None)
        )
    return tuple(descendants)


def _profile_relative_current_directory(
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
    base = _profile_relative_current_directory(arguments, root)
    operands = normalize_pattern_operands(arguments)
    if not operands:
        return (_DiffTraversalRoot(base),)

    candidates: list[_DiffTraversalRoot] = []
    for operand in operands:
        profile_path = base / PurePosixPath(operand)
        if operand == ".":
            candidates.append(_DiffTraversalRoot(base))
            continue

        wildcard_index = next(
            (
                index
                for index, part in enumerate(profile_path.parts)
                if "*" in part
            ),
            None,
        )
        if wildcard_index is not None:
            fixed_parts = profile_path.parts[:wildcard_index]
            fixed = PurePosixPath(*fixed_parts) if fixed_parts else PurePosixPath()
            candidates.append(_DiffTraversalRoot(fixed))
            continue

        local_path = root.joinpath(*profile_path.parts)
        if local_path.is_dir() and not local_path.is_symlink():
            candidates.append(_DiffTraversalRoot(profile_path, include_container=True))
        else:
            candidates.append(_DiffTraversalRoot(profile_path.parent))

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
            "resume directory must be a profile-relative directory"
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
    if arguments.keep_remote:
        command.append("--keep-remote")
    if arguments.recursive:
        command.append("--recursive")
    if arguments.included_only:
        command.append("-i")
    if arguments.show_all:
        command.append("--all")
    command.extend(("--paged", "--resume", directory.as_posix()))
    return shlex.join(command)


def _build_plan(
    arguments: argparse.Namespace,
    root: Path,
    transport: ExplicitFTPSTransport,
    rules: RuleSet,
    *,
    direction: str,
    progress: TextIO,
    include_excluded: bool = False,
) -> tuple[TreeSnapshot, TreeSnapshot, ComparisonPlan]:
    selector = _file_selection(arguments, root)
    prune_remote = direction == "push" and not getattr(
        arguments, "keep_remote", False
    )
    print("Scanning local files...", file=progress, flush=True)
    local = snapshot_local(
        root,
        rules,
        selector,
        include_excluded=include_excluded,
        traverse_excluded=(
            include_excluded
            and prune_remote
            and _recursive_transfer_scope(arguments)
        ),
        respect_remote_boundaries=True,
    )
    remote_selector = (
        _remote_push_selection(arguments, root, local, selector)
        if direction == "push" and prune_remote
        else selector
    )
    expanded_remote_deletion = remote_selector != selector
    print("Reading remote files over FTPS...", file=progress, flush=True)

    def report_recovery(message: str) -> None:
        print(f"  {message}", file=progress, flush=True)

    remote = transport.snapshot(
        rules,
        remote_selector,
        include_excluded=include_excluded,
        traverse_excluded=(
            include_excluded
            and prune_remote
            and (
                _recursive_transfer_scope(arguments)
                or expanded_remote_deletion
            )
        ),
        artifact_recovery=report_recovery if direction == "push" else None,
    )
    print("Comparing local and remote files...", file=progress, flush=True)
    plan = build_comparison(
        local,
        remote,
        direction=direction,
        prune_remote=prune_remote,
        selector=remote_selector if arguments.pattern_operands else None,
    )
    untraversed_directories = frozenset(
        entry.path
        for entry in plan.entries
        if _comparison_entry_kind(entry, direction) == "directory"
        and not remote_selector.may_match_descendant(entry.path)
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
    _, name, profile = _resolve_profile(arguments, store)
    root = _require_local_root(name, profile)
    if arguments.resume is not None and not arguments.paged:
        raise ConfigurationError("--resume requires --paged")
    resume = _resume_directory(arguments.resume)
    selector = _file_selection(arguments, root)
    rules = _effective_rules(store, profile)
    direction = "pull" if arguments.pull else "push"
    prune_remote = direction == "push" and not arguments.keep_remote
    color = _use_color(output)
    print(f"Checking differences for profile '{name}'...", file=progress, flush=True)
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
    pending: list[_PendingDiffDirectory | _PendingDiffOutput] = [
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
    emitted_directories: set[str] = set()
    with ExplicitFTPSTransport(profile) as transport:
        if pending and arguments.show_all:
            for line in _scope_header_lines(
                pending[-1].display_root,
                anchored=pending[-1].display_anchor,
                color=color,
            ):
                print(line, file=output, flush=True)
                displayed_count += 1
        while pending:
            current = pending.pop()
            if isinstance(current, _PendingDiffOutput):
                for line in current.lines:
                    print(line, file=output, flush=True)
                displayed_count += len(current.lines)
                continue
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
                descend_remote_only=prune_remote,
                descend_excluded=(
                    prune_remote and _recursive_transfer_scope(arguments)
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
                excluded = rules.excludes(
                    container_path, target="local", is_directory=True
                )
                remote_excluded = rules.excludes(
                    container_path, target="remote", is_directory=True
                )
                if current.has_local:
                    local = TreeSnapshot(
                        local.entries
                        + (
                            TreeEntry(
                                container_path,
                                "directory",
                                excluded=excluded,
                                remote_excluded=remote_excluded,
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
                                remote_excluded=remote_excluded,
                            ),
                        )
                    )
            selected_count += len(local.entries) + len(remote.entries)
            plan = build_comparison(
                local,
                remote,
                direction=direction,
                prune_remote=prune_remote,
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
            projected_recursive_deletions = frozenset(
                entry.path
                for entry in plan.entries
                if direction == "push"
                and not arguments.pattern_operands
                and not arguments.keep_remote
                and entry.action == "delete-remote"
                and entry.path in collapsed_paths
            )
            plan = mark_untraversed_directories(
                plan,
                collapsed_paths - projected_recursive_deletions,
            )
            shown = tuple(
                entry
                for entry in plan.entries
                if (
                    (
                        arguments.show_all
                        and (
                            not arguments.included_only
                            or entry.action != "excluded"
                        )
                    )
                    or (
                        not arguments.show_all
                        and (
                            entry.action
                            not in {"unchanged", "excluded", "untraversed"}
                            or (
                                entry.action == "excluded"
                                and not arguments.included_only
                            )
                            or (
                                entry.action == "untraversed"
                                and entry.state == "remote-only"
                            )
                        )
                    )
                )
            )

            def format_entries(
                entries: Sequence[ComparisonEntry],
            ) -> tuple[str, ...]:
                if not arguments.show_all:
                    return tuple(
                        line
                        for entry in entries
                        for line in _format_compact_comparison_entry(
                            entry,
                            direction,
                            color=color,
                            collapsed=entry.path in collapsed_paths,
                            display_root=current.display_root,
                            emitted_directories=emitted_directories,
                        )
                    )
                return _format_comparison_entries(
                    entries,
                    direction,
                    color=color,
                    collapsed_paths=collapsed_paths,
                    display_path=lambda path: _scoped_display_path(
                        path,
                        display_root=current.display_root,
                    ),
                )

            if arguments.paged:
                pending.extend(reversed(pending_descendants))
                lines = format_entries(shown)
                for line in lines:
                    print(line, file=output, flush=True)
                displayed_count += len(lines)
                if not lines:
                    print(
                        f"  no differences in {display_directory}",
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

            descendants_by_path = {
                descendant.path.as_posix(): descendant
                for descendant in pending_descendants
            }
            events: list[_PendingDiffDirectory | _PendingDiffOutput] = []
            ordered_entries = _file_browser_order(
                plan.entries,
                path_of=lambda item: item.path,
                directory_of=lambda item: (
                    _comparison_entry_kind(item, direction) == "directory"
                ),
            )
            directory_entries = tuple(
                entry
                for entry in ordered_entries
                if _comparison_entry_kind(entry, direction) == "directory"
            )
            file_entries = tuple(
                entry
                for entry in ordered_entries
                if _comparison_entry_kind(entry, direction) != "directory"
                and entry in shown
            )
            for entry in directory_entries:
                if entry in shown:
                    entry_lines = format_entries((entry,))
                    if entry_lines:
                        events.append(_PendingDiffOutput(entry_lines))
                descendant = descendants_by_path.get(entry.path)
                if descendant is not None:
                    events.append(descendant)
            scheduled_paths = {
                event.path.as_posix()
                for event in events
                if isinstance(event, _PendingDiffDirectory)
            }
            events.extend(
                descendant
                for descendant in pending_descendants
                if descendant.path.as_posix() not in scheduled_paths
            )
            events.extend(
                _PendingDiffOutput(entry_lines)
                for entry in file_entries
                for entry_lines in (format_entries((entry,)),)
                if entry_lines
            )
            pending.extend(reversed(events))

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
            f"{direction} finished with errors for profile '{name}': "
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
            lines.append("Remote-only paths retained by --keep-remote.")
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
    _, name, profile = _resolve_profile(arguments, store)
    root = _require_local_root(name, profile)
    print(
        f"Preparing {arguments.command} for profile '{name}'...",
        file=progress,
        flush=True,
    )
    options = _active_options(arguments)
    if options is not None:
        print(options, file=progress, flush=True)
    print("Connecting securely over FTPS...", file=progress, flush=True)
    with ExplicitFTPSTransport(profile) as transport:
        local, remote, plan = _build_plan(
            arguments,
            root,
            transport,
            _effective_rules(store, profile),
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
        if arguments.command == "create":
            message = _create_profile(arguments, configuration_store, stdin, stdout)
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
        elif arguments.command == "root":
            message = _show_root(arguments, configuration_store)
        elif arguments.command == "profile":
            message = _show_profile(arguments, configuration_store)
        elif arguments.command == "profiles":
            message = _list_profiles(configuration_store)
        elif arguments.command == "list":
            message = (
                _list_remote(arguments, configuration_store, stderr, stdout)
                if arguments.remote
                else _list_local(arguments, configuration_store, stdout)
            )
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

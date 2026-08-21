from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from typing import TextIO

from hls import __version__
from hls.config import (
    ConfigurationError,
    ConfigurationStore,
    ServerConfiguration,
    credential_environment_names,
    validate_config_name,
)
from hls.transport import ExplicitFTPSTransport, TransportError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hls",
        description="Transfer mapped files over explicit FTP over TLS.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="add an FTPS server profile")
    add_parser.add_argument("config_name")
    add_parser.add_argument("type", choices=("ftps",))
    add_parser.add_argument("--host", required=True)
    add_parser.add_argument("--port", type=int, default=21)
    add_parser.add_argument("--username-env")
    add_parser.add_argument("--password-env")

    connect_parser = subparsers.add_parser(
        "connect", help="verify an FTPS connection"
    )
    connect_parser.add_argument("config_name")

    help_parser = subparsers.add_parser("help", help="show command help")
    help_parser.add_argument("topic", nargs="?")

    subparsers.add_parser("version", help="show the installed version")
    return parser


def _save_server(
    arguments: argparse.Namespace,
    store: ConfigurationStore,
) -> str:
    name = validate_config_name(arguments.config_name)
    configuration = store.load()
    if name in configuration.servers:
        raise ConfigurationError(f"configuration '{name}' already exists")
    default_username_env, default_password_env = credential_environment_names(name)
    server = ServerConfiguration(
        type=arguments.type,
        host=arguments.host,
        port=arguments.port,
        username_env=arguments.username_env or default_username_env,
        password_env=arguments.password_env or default_password_env,
    )
    configuration.servers[name] = server
    store.save(configuration)
    return f"Added FTPS configuration '{name}'."


def _resolve_server(
    arguments: argparse.Namespace, store: ConfigurationStore
) -> tuple[str, ServerConfiguration]:
    name = validate_config_name(arguments.config_name)
    configuration = store.load()
    if name not in configuration.servers:
        raise ConfigurationError(f"configuration '{name}' does not exist")
    return name, configuration.servers[name]


def _connect(arguments: argparse.Namespace, store: ConfigurationStore) -> str:
    name, server = _resolve_server(arguments, store)
    with ExplicitFTPSTransport(server):
        pass
    return f"Connected securely using configuration '{name}'."


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
            message = _save_server(arguments, configuration_store)
        elif arguments.command == "connect":
            message = _connect(arguments, configuration_store)
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

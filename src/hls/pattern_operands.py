from __future__ import annotations

import argparse


class PatternOperandError(ValueError):
    """Raised when shared CLI path-pattern operands are malformed."""


def add_pattern_operands(
    parser: argparse.ArgumentParser,
    *,
    required: bool,
    help_text: str,
    metavar: str = "pattern",
) -> None:
    parser.add_argument(
        "pattern_operands",
        nargs="+" if required else "*",
        metavar=metavar,
        help=help_text,
    )


def normalize_pattern_operands(arguments: argparse.Namespace) -> tuple[str, ...]:
    patterns: list[str] = []
    for operand in arguments.pattern_operands:
        for value in operand.split(","):
            normalized = value.strip()
            if not normalized:
                raise PatternOperandError("path patterns cannot be empty")
            patterns.append(normalized)
    return tuple(patterns)

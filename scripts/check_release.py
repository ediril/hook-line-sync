#!/usr/bin/env python3
"""Validate release identity before building or publishing distributions."""

from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "src" / "hls" / "__init__.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"

VERSION_PATTERN = re.compile(
    r'^__version__ = "(?P<version>0\.(?P<month>[1-9]|1[0-2])\.'
    r'(?P<day>[1-9]|[12][0-9]|3[01])\.(?P<increment>[1-9][0-9]*))"$',
    re.MULTILINE,
)


def release_version() -> tuple[str, int, int]:
    matches = tuple(VERSION_PATTERN.finditer(VERSION_FILE.read_text()))
    if len(matches) != 1:
        raise SystemExit(
            "release check failed: src/hls/__init__.py must contain exactly one "
            'valid __version__ = "0.<month>.<day>.<increment>" assignment'
        )
    match = matches[0]
    return match["version"], int(match["month"]), int(match["day"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tag",
        help="release tag to verify; must be v followed by the package version",
    )
    arguments = parser.parse_args()

    version, month, day = release_version()
    if arguments.tag is not None and arguments.tag != f"v{version}":
        raise SystemExit(
            f"release check failed: tag {arguments.tag!r} does not match v{version}"
        )

    heading_pattern = re.compile(
        rf"^## {re.escape(version)} — (?P<year>[0-9]{{4}})-"
        rf"{month:02d}-{day:02d}$",
        re.MULTILINE,
    )
    heading = heading_pattern.search(CHANGELOG_FILE.read_text())
    if heading is None:
        raise SystemExit(
            f"release check failed: CHANGELOG.md has no dated {version} heading"
        )

    release_date = date(int(heading["year"]), month, day)
    print(f"Release identity valid: {version} ({release_date.isoformat()})")


if __name__ == "__main__":
    main()

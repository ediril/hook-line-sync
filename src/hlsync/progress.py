"""Directory progress based on work discovered by the remote traversal."""

from __future__ import annotations

import os
import shutil
from pathlib import PurePosixPath
from typing import TextIO


class DirectoryReadProgress:
    def __init__(self, output: TextIO) -> None:
        self.output = output
        self.terminal = output.isatty() and os.environ.get("TERM") != "dumb"
        self.directory = "."
        self.completed = 0
        self.discovered = 1

    def _draw(self) -> None:
        text = (
            f"  {self.completed}/{self.discovered} discovered directories read"
            f" · {self.directory}/"
        )
        if self.terminal:
            width = max(1, shutil.get_terminal_size().columns - 1)
            print(f"\r\033[2K{text[:width]}", end="", file=self.output, flush=True)
        else:
            print(text, file=self.output, flush=True)

    def __enter__(self) -> DirectoryReadProgress:
        return self

    def reading(self, directory: PurePosixPath) -> None:
        self.directory = directory.as_posix()
        self._draw()

    def counts(self, completed: int, discovered: int) -> None:
        self.completed = completed
        self.discovered = discovered
        if self.terminal:
            self._draw()

    def message(self, message: str) -> None:
        if self.terminal:
            print("\r\033[2K", end="", file=self.output)
        print(f"  {message}", file=self.output, flush=True)
        if self.terminal:
            self._draw()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.terminal:
            print("\r\033[2K", end="", file=self.output, flush=True)
        if exc_type is None:
            print(
                f"  Read {self.completed}/{self.discovered} directories.",
                file=self.output, flush=True,
            )

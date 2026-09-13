"""Terminal feedback for directory reads whose total is not yet known."""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import PurePosixPath
from typing import TextIO


class DirectoryReadProgress:
    def __init__(self, output: TextIO) -> None:
        self.output = output
        self.terminal = output.isatty() and os.environ.get("TERM") != "dumb"
        self.directory = "."
        self.started = 0
        self.frame = 0
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None

    def _draw(self) -> None:
        position = self.frame % 26
        position = position if position <= 13 else 26 - position
        bar = "-" * position + "###" + "-" * (13 - position)
        text = (
            f"  [{bar}] Reading {self.directory} · "
            f"{max(0, self.started - 1)} directories read"
        )
        width = max(1, shutil.get_terminal_size().columns - 1)
        print(f"\r\033[2K{text[:width]}", end="", file=self.output, flush=True)
        self.frame += 1

    def _animate(self) -> None:
        while not self.stop.wait(0.1):
            with self.lock:
                self._draw()

    def __enter__(self) -> DirectoryReadProgress:
        if self.terminal:
            self._draw()
            self.thread = threading.Thread(target=self._animate, daemon=True)
            self.thread.start()
        return self

    def reading(self, directory: PurePosixPath) -> None:
        with self.lock:
            self.directory = directory.as_posix()
            self.started += 1
            if self.terminal:
                self._draw()
            else:
                print(f"  Reading {self.directory}", file=self.output, flush=True)

    def message(self, message: str) -> None:
        with self.lock:
            if self.terminal:
                print("\r\033[2K", end="", file=self.output)
            print(f"  {message}", file=self.output, flush=True)
            if self.terminal:
                self._draw()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop.set()
        if self.thread is not None:
            self.thread.join()
        if self.terminal:
            print("\r\033[2K", end="", file=self.output, flush=True)
            if exc_type is None:
                print(
                    f"  Read {self.started} directories.",
                    file=self.output, flush=True,
                )

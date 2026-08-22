#!/usr/bin/env python3
"""Build and validate release artifacts without publishing them."""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from check_release import validate_release

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    print(f"\n> {shlex.join(arguments)}", flush=True)
    subprocess.run(arguments, cwd=ROOT, check=True)


def installed_hls(venv: Path) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return venv / directory / f"hls{suffix}"


def venv_python(venv: Path) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    return venv / directory / name


def main() -> None:
    version = validate_release()
    destination = ROOT / "dist" / version
    if destination.exists():
        raise SystemExit(
            f"release preparation stopped: {destination.relative_to(ROOT)} "
            "already exists"
        )

    destination.parent.mkdir(exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{version}-", dir=destination.parent)
    )
    try:
        run(sys.executable, "-m", "ruff", "check", ".")
        run(sys.executable, "-m", "pytest")
        run(sys.executable, "-m", "build", "--outdir", os.fspath(staging))

        wheels = tuple(staging.glob("*.whl"))
        source_archives = tuple(staging.glob("*.tar.gz"))
        if len(wheels) != 1 or len(source_archives) != 1:
            raise SystemExit(
                "release preparation stopped: expected exactly one wheel and "
                "one source archive"
            )
        artifacts = (*wheels, *source_archives)
        run(sys.executable, "-m", "twine", "check", *(map(os.fspath, artifacts)))

        with tempfile.TemporaryDirectory(prefix="hls-install-check-") as temp:
            venv = Path(temp) / "venv"
            run(sys.executable, "-m", "venv", os.fspath(venv))
            run(
                os.fspath(venv_python(venv)),
                "-m",
                "pip",
                "install",
                os.fspath(wheels[0]),
            )
            output = subprocess.check_output(
                [os.fspath(installed_hls(venv)), "--version"],
                cwd=ROOT,
                text=True,
            ).strip()
            if output != version:
                raise SystemExit(
                    "release preparation stopped: installed CLI reported "
                    f"{output!r}, expected {version!r}"
                )
            print(f"Installed CLI version valid: {output}")

        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    relative_destination = destination.relative_to(ROOT)
    print(f"\nRelease {version} is ready in {relative_destination}/")
    print(f"Publish manually: python -m twine upload {relative_destination}/*")


if __name__ == "__main__":
    main()

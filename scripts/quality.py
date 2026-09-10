#!/usr/bin/env python3
"""Run the repository's fast, release-blocking quality checks."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_DIRECTORY = PROJECT_ROOT / "easyprent_accounting" / "static"
PACKAGE_IMPORTS = (
    "easyprent_accounting.cli",
    "easyprent_accounting.db",
    "easyprent_accounting.server",
    "easyprent_accounting.web",
)


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("node is required for JavaScript syntax checks", file=sys.stderr)
        return 1

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    for source_file in sorted(STATIC_DIRECTORY.glob("*.js")):
        run([node, "--check", str(source_file)])
    run(
        [
            sys.executable,
            "-c",
            "import " + ", ".join(PACKAGE_IMPORTS),
        ]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

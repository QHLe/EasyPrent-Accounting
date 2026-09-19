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
    "easyprent_accounting.deployment",
    "easyprent_accounting.packaging",
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

    npm = shutil.which("npm")
    if npm is None:
        print("npm is required for reproducible Node dependency installation", file=sys.stderr)
        return 1

    node_manifests = (
        PROJECT_ROOT / "package.json",
        PROJECT_ROOT / "package-lock.json",
    )
    missing_manifests = [path.name for path in node_manifests if not path.is_file()]
    if missing_manifests:
        print(
            "required Node manifest files are missing: " + ", ".join(missing_manifests),
            file=sys.stderr,
        )
        return 1

    run([npm, "ci", "--ignore-scripts"])
    run([npm, "run", "typecheck"])
    run([npm, "run", "test"])
    run([npm, "run", "build"])

    run([sys.executable, "scripts/export_openapi.py"])
    run([npm, "run", "generate-api"])
    run(["git", "diff", "--exit-code", "openapi.json", "src/api/schema.d.ts"])

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

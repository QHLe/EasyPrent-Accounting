from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import zipfile


FRONTEND_FILES = ("package.json", "package-lock.json", "vite.config.ts", "index.html", "tsconfig.json")


def _frontend_assets(names: list[str]) -> set[str]:
    return {
        name for name in names
        if name.startswith("easyprent_accounting/static_dist/assets/")
        and not name.endswith("/")
    }


def assert_wheel_is_clean(wheel_path: Path) -> None:
    """Assert that a built wheel contains no forbidden legacy paths like src/."""
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        forbidden = [name for name in names if name.startswith("src/") or name.startswith("build/")]
        if forbidden:
            raise ValueError(f"Built wheel contains forbidden paths: {forbidden}")

        required = {
            "easyprent_accounting/__init__.py",
            "easyprent_accounting/config.py",
            "easyprent_accounting/static_dist/index.html",
            "easyprent_accounting/templates/utility_settlement.ods",
        }
        missing = required.difference(names)
        if missing:
            raise ValueError(f"Built wheel is missing canonical easyprent_accounting package: {names}")
        assets = _frontend_assets(names)
        if not assets:
            raise ValueError("Built wheel contains no Vite assets")
        index = archive.read("easyprent_accounting/static_dist/index.html").decode("utf-8")
        if not any(
            "/" + asset.removeprefix("easyprent_accounting/static_dist/") in index
            for asset in assets
        ):
            raise ValueError("Built wheel index does not reference a packaged Vite asset")


def validate_install_target_writable() -> None:
    """Reject mixed-owner venvs before pip replaces packages or metadata.

    This runs inside the target interpreter as the account that will run pip.
    Checking each existing directory matters: a writable site-packages parent
    does not make a root-owned package subtree safe to uninstall or replace.
    """
    site_packages = Path(sysconfig.get_path("purelib")).resolve()
    # The venv interpreter commonly symlinks /usr/bin/python; keep the venv
    # path instead of following that symlink into the system bin directory.
    venv_bin = Path(sys.executable).absolute().parent
    roots = [site_packages, venv_bin]
    for package_name in ("easyprent_accounting", "src", "pip"):
        roots.append(site_packages / package_name)
    for pattern in (
        "easyprent_accounting-*.dist-info",
        "easy_rem-*.dist-info",
        "pip-*.dist-info",
    ):
        roots.extend(site_packages.glob(pattern))

    for root in roots:
        if not root.exists():
            continue
        if not root.is_dir():
            raise RuntimeError(f"Installation target is not a directory: {root}")
        directories = (root, *(path for path in root.rglob("*") if path.is_dir()))
        for directory in directories:
            if not os.access(directory, os.W_OK | os.X_OK):
                raise PermissionError(
                    f"Installation target is not writable as the checkout owner: {directory}. "
                    "Inspect ownership and permissions of the existing .venv; "
                    "no automatic chown will be performed."
                )


def uninstall_legacy_distribution(python_executable: str = sys.executable) -> None:
    """Explicitly uninstall legacy easy-rem distribution if present."""
    subprocess.run(
        [python_executable, "-m", "pip", "uninstall", "-y", "easy-rem"],
        check=True,
    )
    remaining = subprocess.run(
        [python_executable, "-m", "pip", "show", "easy-rem"],
        capture_output=True,
        text=True,
    )
    if remaining.returncode == 0:
        raise RuntimeError("Legacy easy-rem distribution is still installed")
    with tempfile.TemporaryDirectory(prefix="easyprent-legacy-check-") as foreign_dir:
        subprocess.run(
            [
                python_executable,
                "-I",
                "-c",
                """
from importlib import metadata, util
try:
    metadata.distribution("easy-rem")
except metadata.PackageNotFoundError:
    pass
else:
    raise AssertionError("easy-rem metadata remains installed")
try:
    legacy = util.find_spec("src.easyprent_accounting")
except ModuleNotFoundError:
    legacy = None
assert legacy is None, "legacy src.easyprent_accounting namespace remains importable"
""",
            ],
            cwd=foreign_dir,
            check=True,
        )


def build_clean_wheel(
    project_root: Path,
    output_dir: Path,
    python_executable: str = sys.executable,
) -> Path:
    """Build and validate a wheel from an isolated copy of the project source."""
    project_root = project_root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    existing_wheels = list(output_dir.glob("easyprent_accounting-*.whl"))
    if existing_wheels:
        raise FileExistsError(f"Wheel output directory is not empty: {output_dir}")

    with tempfile.TemporaryDirectory(prefix="easyprent-build-") as temp_dir:
        build_root = Path(temp_dir) / "source"
        build_root.mkdir()
        for filename in ("pyproject.toml", "README.md"):
            source_file = project_root / filename
            if not source_file.is_file():
                raise FileNotFoundError(f"Required build file is missing: {source_file}")
            shutil.copy2(source_file, build_root / filename)

        package_source = project_root / "easyprent_accounting"
        if not package_source.is_dir():
            raise FileNotFoundError(f"Canonical package directory is missing: {package_source}")
        shutil.copytree(
            package_source,
            build_root / "easyprent_accounting",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.egg-info", "static_dist"),
        )

        for filename in FRONTEND_FILES:
            source_file = project_root / filename
            if not source_file.is_file():
                raise FileNotFoundError(f"Required frontend build file is missing: {source_file}")
            shutil.copy2(source_file, build_root / filename)
        frontend_source = project_root / "src"
        if not frontend_source.is_dir():
            raise FileNotFoundError(f"Frontend source is missing: {frontend_source}")
        shutil.copytree(frontend_source, build_root / "src")
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("npm is required to build a distributable wheel")
        for command in ([npm, "ci", "--ignore-scripts"], [npm, "run", "build"]):
            completed = subprocess.run(command, capture_output=True, text=True, cwd=build_root)
            if completed.returncode != 0:
                raise RuntimeError(
                    f"Frontend build failed ({' '.join(command)}):\n"
                    f"{completed.stderr}\n{completed.stdout}"
                )

        cmd = [
            python_executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "-w",
            str(output_dir),
            str(build_root),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, cwd=build_root)
        if completed.returncode != 0:
            raise RuntimeError(f"Failed to build wheel:\n{completed.stderr}\n{completed.stdout}")

        wheels = sorted(output_dir.glob("easyprent_accounting-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected exactly one easyprent_accounting wheel in {output_dir}, found: {wheels}")

        wheel_path = wheels[0]
        assert_wheel_is_clean(wheel_path)
        return wheel_path


def _installed_package_matches_wheel(
    wheel_path: Path,
    python_executable: str,
) -> None:
    with zipfile.ZipFile(wheel_path) as archive:
        checked_names = [
            "easyprent_accounting/config.py",
            "easyprent_accounting/templates/utility_settlement.ods",
            "easyprent_accounting/static_dist/index.html",
            *sorted(_frontend_assets(archive.namelist())),
        ]
        expected_hashes = {
            name.removeprefix("easyprent_accounting/"): hashlib.sha256(archive.read(name)).hexdigest()
            for name in checked_names
        }

    script = """
import hashlib
from importlib import metadata, resources

assert metadata.distribution("easyprent-accounting")
package = resources.files("easyprent_accounting")
for name, expected_hash in expected_hashes.items():
    actual_hash = hashlib.sha256(package.joinpath(name).read_bytes()).hexdigest()
    assert actual_hash == expected_hash, name
"""
    # -I discards the caller's CWD and PYTHONPATH, so a stale installed wheel
    # cannot be hidden by the freshly pulled checkout source.
    script = (
        f"expected_hashes = {expected_hashes!r}\n"
        + script
    )
    with tempfile.TemporaryDirectory(prefix="easyprent-verify-") as foreign_dir:
        subprocess.run(
            [python_executable, "-I", "-c", script],
            cwd=foreign_dir,
            check=True,
        )


def _legacy_package_directory(python_executable: str) -> Path | None:
    with tempfile.TemporaryDirectory(prefix="easyprent-legacy-locate-") as foreign_dir:
        completed = subprocess.run(
            [
                python_executable,
                "-I",
                "-c",
                """
from importlib import util
try:
    spec = util.find_spec("src.easyprent_accounting")
except ModuleNotFoundError:
    spec = None
if spec is not None and spec.submodule_search_locations:
    print(next(iter(spec.submodule_search_locations)))
""",
            ],
            cwd=foreign_dir,
            capture_output=True,
            text=True,
            check=True,
        )
    location = completed.stdout.strip()
    if not location:
        return None
    package_dir = Path(location).resolve()
    venv_root = Path(python_executable).absolute().parent.parent
    if not package_dir.is_relative_to(venv_root) or not package_dir.is_dir():
        raise RuntimeError(f"Legacy package path is outside the target venv: {package_dir}")
    return package_dir


def _restore_missing_legacy_files(backup: Path, original: Path) -> None:
    """Keep the old unit restartable until a successful systemd cutover."""
    for item in backup.rglob("*"):
        target = original / item.relative_to(backup)
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def install_checkout(
    project_root: Path,
    python_executable: str = sys.executable,
) -> None:
    """Build, install, and verify the canonical package from a checkout.

    Legacy package retirement is deliberately separate: the caller must first
    move any active systemd unit off the old src-based command.
    """
    validate_install_target_writable()
    with tempfile.TemporaryDirectory(prefix="easyprent-wheel-") as wheel_dir:
        wheel_path = build_clean_wheel(
            project_root,
            Path(wheel_dir),
            python_executable=python_executable,
        )
        legacy_dir = _legacy_package_directory(python_executable)
        backup = Path(wheel_dir) / "legacy-backup"
        if legacy_dir is not None:
            shutil.copytree(legacy_dir, backup, symlinks=True)
        try:
            subprocess.run(
                [python_executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
                check=True,
            )
            # Pip's upgrade flag skips a same-version package; force activation
            # of the exact clean wheel while retaining installed dependencies.
            subprocess.run(
                [
                    python_executable,
                    "-m",
                    "pip",
                    "install",
                    "--force-reinstall",
                    "--no-deps",
                    str(wheel_path),
                ],
                check=True,
            )
            _installed_package_matches_wheel(wheel_path, python_executable)
        finally:
            if legacy_dir is not None:
                _restore_missing_legacy_files(backup, legacy_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canonical EasyPrent wheel installation")
    parser.add_argument("command", choices=("preflight-install", "build", "install", "retire-legacy"))
    parser.add_argument("project_root", nargs="?", type=Path)
    args = parser.parse_args(argv)
    if args.command == "preflight-install":
        if args.project_root is not None:
            parser.error("preflight-install takes no project root")
        validate_install_target_writable()
    elif args.command == "build":
        if args.project_root is None:
            parser.error("build requires PROJECT_ROOT")
        with tempfile.TemporaryDirectory(prefix="easyprent-build-check-") as wheel_dir:
            wheel_path = build_clean_wheel(args.project_root, Path(wheel_dir))
            print(f"Distributable wheel verified: {wheel_path.name}")
    elif args.command == "install":
        if args.project_root is None:
            parser.error("install requires PROJECT_ROOT")
        install_checkout(args.project_root)
    else:
        if args.project_root is not None:
            parser.error("retire-legacy takes no project root")
        uninstall_legacy_distribution()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

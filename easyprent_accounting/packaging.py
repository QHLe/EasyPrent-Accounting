from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def clean_build_artifacts(project_root: Path) -> None:
    """Purge legacy and transient build directories to prevent dirty packaging."""
    for item in ["build", "dist"]:
        path = project_root / item
        if path.is_dir():
            shutil.rmtree(path)
        elif path.is_file():
            path.unlink()

    for egg_info in project_root.glob("*.egg-info"):
        if egg_info.is_dir():
            shutil.rmtree(egg_info)
        elif egg_info.is_file():
            egg_info.unlink()


def assert_wheel_is_clean(wheel_path: Path) -> None:
    """Assert that a built wheel contains no forbidden legacy paths like src/."""
    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        forbidden = [name for name in names if name.startswith("src/") or name.startswith("build/")]
        if forbidden:
            raise ValueError(f"Built wheel contains forbidden paths: {forbidden}")
        
        has_canonical = any(name.startswith("easyprent_accounting/") for name in names)
        if not has_canonical:
            raise ValueError(f"Built wheel is missing canonical easyprent_accounting package: {names}")


def uninstall_legacy_distribution(python_executable: str = sys.executable) -> None:
    """Explicitly uninstall legacy easy-rem distribution if present."""
    subprocess.run(
        [python_executable, "-m", "pip", "uninstall", "-y", "easy-rem"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def build_clean_wheel(
    project_root: Path,
    output_dir: Path,
    python_executable: str = sys.executable,
) -> Path:
    """Clean artifacts, build wheel with no isolation/deps, and verify its purity."""
    clean_build_artifacts(project_root)
    try:
        cmd = [
            python_executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(output_dir),
            str(project_root),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
        if completed.returncode != 0:
            raise RuntimeError(f"Failed to build wheel:\n{completed.stderr}\n{completed.stdout}")

        wheels = sorted(output_dir.glob("easyprent_accounting-*.whl"))
        if not wheels:
            raise FileNotFoundError(f"No easyprent_accounting wheel found in {output_dir}")

        wheel_path = wheels[-1]
        assert_wheel_is_clean(wheel_path)
        return wheel_path
    finally:
        clean_build_artifacts(project_root)


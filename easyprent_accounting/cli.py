from __future__ import annotations

import argparse
import os
import pwd
import shlex
import signal
import subprocess
import sys
import time
from .config import load_config, get_global_config, set_global_config
from .deployment import (
    CANONICAL_SERVICE_NAME,
    DEFAULT_UNIT_DIRECTORY,
    LEGACY_SERVICE_NAME,
    deploy_systemd_unit,
    validate_systemd_unit,
)
from .packaging import install_checkout, uninstall_legacy_distribution
from pathlib import Path

from .server import DEFAULT_PORT


def runtime_dir() -> Path:
    return get_global_config().project_root / ".easyprent"


def pid_file() -> Path:
    return runtime_dir() / "server.pid"


def log_file() -> Path:
    return runtime_dir() / "server.log"


def runtime_python() -> str:
    venv_python = get_global_config().project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def server_command() -> list[str]:
    return [runtime_python(), "-m", "easyprent_accounting.server"]


def ensure_runtime_dir() -> None:
    runtime_dir().mkdir(exist_ok=True)


def read_pid() -> int | None:
    try:
        raw_pid = pid_file().read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if not raw_pid.isdigit():
        pid_file().unlink(missing_ok=True)
        return None
    return int(raw_pid)


def write_pid(pid: int) -> None:
    ensure_runtime_dir()
    pid_file().write_text(f"{pid}\n", encoding="utf-8")


def remove_pid_file() -> None:
    pid_file().unlink(missing_ok=True)


def is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def running_pid() -> int | None:
    pid = read_pid()
    if pid is None:
        return None
    if is_running(pid):
        return pid
    remove_pid_file()
    return None


def start_server(env: dict[str, str]) -> int:
    pid = running_pid()
    if pid is not None:
        print(f"Server laeuft bereits mit PID {pid}.")
        return 0

    cfg = get_global_config()
    child_env = env.copy()
    child_env["EASYPRENT_PROJECT_ROOT"] = str(cfg.project_root)
    child_env["EASYPRENT_DB_PATH"] = str(cfg.db_path)

    ensure_runtime_dir()
    with log_file().open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            server_command(),
            cwd=cfg.project_root,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=child_env,
        )
    time.sleep(0.5)
    if process.poll() is not None:
        remove_pid_file()
        print(f"Serverstart fehlgeschlagen. Details stehen in {log_file()}.", file=sys.stderr)
        return process.returncode or 1
    write_pid(process.pid)
    print(f"Server gestartet auf http://localhost:{DEFAULT_PORT} (PID {process.pid}).")
    print(f"Logdatei: {log_file()}")
    return 0


def stop_server() -> int:
    pid = running_pid()
    if pid is None:
        print("Server ist nicht gestartet.")
        return 0

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        remove_pid_file()
        print("Serverprozess war bereits beendet.")
        return 0

    deadline = time.time() + 10
    while time.time() < deadline:
        if not is_running(pid):
            remove_pid_file()
            print("Server gestoppt.")
            return 0
        time.sleep(0.2)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass

    remove_pid_file()
    print("Server wurde zwangsweise beendet.")
    return 0


def restart_server(env: dict[str, str]) -> int:
    stop_code = stop_server()
    if stop_code != 0:
        return stop_code
    return start_server(env)


def run_command(command: list[str]) -> int:
    print(f"$ {shlex.join(command)}")
    completed = subprocess.run(command, cwd=get_global_config().project_root)
    return completed.returncode


def _run_as_checkout_owner(command: list[str], root: Path) -> int:
    """Keep Git and venv writes owned by the checkout owner under sudo."""
    owner_uid = root.stat().st_uid
    if os.geteuid() != 0 or owner_uid == 0:
        return run_command(command)
    owner = pwd.getpwuid(owner_uid)
    owner_env = os.environ.copy()
    owner_env.update(HOME=owner.pw_dir, USER=owner.pw_name, LOGNAME=owner.pw_name)
    print(f"$ [{owner.pw_name}] {shlex.join(command)}")
    completed = subprocess.run(
        command,
        cwd=root,
        env=owner_env,
        user=owner_uid,
        group=owner.pw_gid,
        extra_groups=os.getgrouplist(owner.pw_name, owner.pw_gid),
    )
    return completed.returncode


def _install_as_checkout_owner(root: Path, venv_python: Path) -> None:
    owner_uid = root.stat().st_uid
    if os.geteuid() != 0 or owner_uid == 0:
        install_checkout(root, python_executable=str(venv_python))
        return
    if _run_as_checkout_owner(
        [
            str(venv_python),
            "-m",
            "easyprent_accounting.packaging",
            "install",
            str(root),
        ],
        root,
    ) != 0:
        raise RuntimeError("Packaging-Installation als Checkout-Eigentümer fehlgeschlagen")


def _retire_as_checkout_owner(root: Path, venv_python: Path) -> None:
    owner_uid = root.stat().st_uid
    if os.geteuid() != 0 or owner_uid == 0:
        uninstall_legacy_distribution(str(venv_python))
        return
    if _run_as_checkout_owner(
        [str(venv_python), "-m", "easyprent_accounting.packaging", "retire-legacy"],
        root,
    ) != 0:
        raise RuntimeError("Legacy-Paket konnte als Checkout-Eigentümer nicht entfernt werden")


def installed_systemd_unit() -> Path | None:
    canonical = DEFAULT_UNIT_DIRECTORY / CANONICAL_SERVICE_NAME
    legacy = DEFAULT_UNIT_DIRECTORY / LEGACY_SERVICE_NAME
    if canonical.is_file() or canonical.is_symlink():
        return canonical
    if legacy.is_file() or legacy.is_symlink():
        return legacy
    return None


def runtime_user_for_unit(unit_path: Path) -> str:
    for line in unit_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("User="):
            return line.partition("=")[2].strip()
    return pwd.getpwuid(os.geteuid()).pw_name


def project_root_for_unit(unit_path: Path) -> Path:
    for line in unit_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("WorkingDirectory="):
            raw_path = line.partition("=")[2].strip().replace("%%", "%")
            if not raw_path.startswith("/"):
                raise ValueError(f"Unit hat keinen absoluten Projektpfad: {unit_path}")
            return Path(raw_path).resolve()
    raise ValueError(f"Unit enthält kein WorkingDirectory: {unit_path}")


def systemd_unit_is_active() -> bool:
    for name in (CANONICAL_SERVICE_NAME, LEGACY_SERVICE_NAME):
        completed = subprocess.run(
            ["systemctl", "is-active", "--quiet", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode == 0:
            return True
    return False


def finish_update(env: dict[str, str]) -> int:
    root = get_global_config().project_root
    was_running = running_pid() is not None
    unit_path = installed_systemd_unit()
    systemd_was_active = False
    runtime_user: str | None = None
    if unit_path is not None:
        if os.geteuid() != 0:
            print(
                "Systemd-Update erfordert root-Rechte; bitte den Update-Befehl mit sudo ausführen.",
                file=sys.stderr,
            )
            return 1
        try:
            unit_root = project_root_for_unit(unit_path)
            if unit_root != root.resolve():
                raise ValueError(
                    f"Unit gehört zu {unit_root}, nicht zu diesem Checkout {root}"
                )
            systemd_was_active = systemd_unit_is_active()
            if was_running and systemd_was_active:
                raise RuntimeError("Systemd- und CLI-Server laufen gleichzeitig")
            runtime_user = runtime_user_for_unit(unit_path)
            validate_systemd_unit(root, runtime_user)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Systemd-Preflight fehlgeschlagen: {exc}", file=sys.stderr)
            return 1

    venv_python = root / ".venv" / "bin" / "python"
    if venv_python.exists():
        try:
            _install_as_checkout_owner(root, venv_python)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Python-Installation fehlgeschlagen: {exc}", file=sys.stderr)
            return 1

    if unit_path is not None:
        try:
            assert runtime_user is not None
            deploy_systemd_unit(
                root,
                runtime_user,
                start_if_inactive=False,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"Systemd-Umstellung fehlgeschlagen: {exc}", file=sys.stderr)
            return 1

    if venv_python.exists():
        try:
            _retire_as_checkout_owner(root, venv_python)
        except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"Legacy-Paket konnte nicht entfernt werden: {exc}", file=sys.stderr)
            return 1

    if was_running:
        print("Server war aktiv und wird neu gestartet.")
        return restart_server(env)

    if unit_path is not None:
        print("Systemd-Dienst aktualisiert und bei Bedarf neu gestartet.")
        return 0

    print("Update abgeschlossen.")
    return 0


def update_project(env: dict[str, str]) -> int:
    root = get_global_config().project_root
    git_check = subprocess.run(
        [
            "git", "-c", f"safe.directory={root.resolve()}",
            "rev-parse", "--show-toplevel",
        ],
        cwd=root,
        stdout=subprocess.PIPE,
        text=True,
        stderr=subprocess.DEVNULL,
    )
    if git_check.returncode != 0 or Path(git_check.stdout.strip()).resolve() != root.resolve():
        print("Update nicht moeglich: dieses Verzeichnis ist kein gueltiges Git-Checkout.", file=sys.stderr)
        return 1

    if _run_as_checkout_owner(["git", "pull", "--ff-only"], root) != 0:
        return 1

    venv_python = root / ".venv" / "bin" / "python"
    python_executable = str(venv_python) if venv_python.exists() else sys.executable
    # Re-enter through the pulled checkout; the importing CLI process may
    # still contain pre-pull code and must not perform the new installation.
    return run_command(
        [python_executable, "-m", "easyprent_accounting.cli", "finish-update"]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EasyPrent Accounting CLI")
    parser.add_argument(
        "command", choices=("start", "stop", "restart", "update", "finish-update")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    env = os.environ.copy()
    set_global_config(load_config(env))
    args = build_parser().parse_args(argv)
    if args.command == "start":
        return start_server(env)
    if args.command == "stop":
        return stop_server()
    if args.command == "restart":
        return restart_server(env)
    if args.command == "finish-update":
        return finish_update(env)
    return update_project(env)


if __name__ == "__main__":
    raise SystemExit(main())

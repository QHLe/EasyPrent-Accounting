from __future__ import annotations

import argparse
import os
import shlex
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .server import DEFAULT_PORT


SYSTEMD_SERVICE_NAME = "easy-prent.service"


def resolve_project_root() -> Path:
    env_root = os.environ.get("EASY_REM_ROOT")
    if env_root:
        return Path(env_root).resolve()

    cwd = Path.cwd().resolve()
    if (cwd / "src" / "easyprent_accounting").exists():
        return cwd

    return Path(__file__).resolve().parents[2]


def project_root() -> Path:
    return resolve_project_root()


def runtime_dir() -> Path:
    return project_root() / ".easyprent"


def pid_file() -> Path:
    return runtime_dir() / "server.pid"


def log_file() -> Path:
    return runtime_dir() / "server.log"


def runtime_python() -> str:
    venv_python = project_root() / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def server_command() -> list[str]:
    return [runtime_python(), "-m", "src.easyprent_accounting.server"]


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


def start_server() -> int:
    pid = running_pid()
    if pid is not None:
        print(f"Server laeuft bereits mit PID {pid}.")
        return 0

    ensure_runtime_dir()
    with log_file().open("a", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            server_command(),
            cwd=project_root(),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
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


def restart_server() -> int:
    stop_code = stop_server()
    if stop_code != 0:
        return stop_code
    return start_server()


def run_command(command: list[str]) -> int:
    print(f"$ {shlex.join(command)}")
    completed = subprocess.run(command, cwd=project_root())
    return completed.returncode


def systemd_service_is_running() -> bool:
    if shutil.which("systemctl") is None:
        return False
    completed = subprocess.run(
        ["systemctl", "is-active", "--quiet", SYSTEMD_SERVICE_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def update_project() -> int:
    was_running = running_pid() is not None
    systemd_service_was_running = systemd_service_is_running()
    git_check = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=project_root(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if git_check.returncode != 0:
        print("Update nicht moeglich: dieses Verzeichnis ist kein gueltiges Git-Checkout.", file=sys.stderr)
        return 1

    if run_command(["git", "pull", "--ff-only"]) != 0:
        return 1

    package_lock = project_root() / "package-lock.json"
    package_json = project_root() / "package.json"
    if package_json.exists() and package_lock.exists():
        if shutil.which("npm") is None:
            print(
                "Warnung: npm ist nicht installiert; überspringe npm install.",
                file=sys.stderr,
            )
        elif run_command(["npm", "install"]) != 0:
            return 1

    venv_pip = project_root() / ".venv" / "bin" / "pip"
    if venv_pip.exists():
        if run_command([str(venv_pip), "install", "--upgrade", "."]) != 0:
            return 1

    if systemd_service_was_running:
        print("Systemd-Dienst war aktiv und wird neu gestartet.")
        return run_command(["systemctl", "restart", SYSTEMD_SERVICE_NAME])

    if was_running:
        print("Server war aktiv und wird neu gestartet.")
        return restart_server()

    print("Update abgeschlossen.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EasyPrent Accounting CLI")
    parser.add_argument("command", choices=("start", "stop", "restart", "update"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "start":
        return start_server()
    if args.command == "stop":
        return stop_server()
    if args.command == "restart":
        return restart_server()
    return update_project()


if __name__ == "__main__":
    raise SystemExit(main())

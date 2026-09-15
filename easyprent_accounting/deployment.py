"""Render and safely replace the application's systemd unit.

The package installer must install and verify the new wheel before calling this
module. It may remove the old ``easy-rem`` distribution only after deployment
returns successfully; a failed unit cutover leaves that package available for
rollback.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import re
import shlex
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CANONICAL_SERVICE_NAME = "easyprent-accounting.service"
LEGACY_SERVICE_NAME = "easy-prent.service"
DEFAULT_UNIT_DIRECTORY = Path("/etc/systemd/system")

CommandRunner = Callable[[list[str]], int]
HealthProbe = Callable[[], bool]
Sleeper = Callable[[float], None]

HEALTH_URL = "http://127.0.0.1:8020/api/health"
HEALTH_ATTEMPTS = 21
HEALTH_RETRY_SECONDS = 0.25
HEALTH_STABILITY_SECONDS = 1.0


def _subprocess_runner(command: list[str]) -> int:
    return subprocess.run(command, check=False).returncode


def _systemd_string(value: str, *, command: bool = False) -> str:
    """Quote a single systemd value, not a shell token.

    Systemd interprets C-style escapes and percent specifiers in unit values;
    ExecStart additionally expands dollar-prefixed environment variables.
    """
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("systemd values may not contain control characters")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    if command:
        escaped = escaped.replace("$", "$$")
    return f'"{escaped}"'


def _systemd_path(value: str) -> str:
    """Keep path directives unquoted; systemd treats quotes as path bytes."""
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("systemd paths may not contain control characters")
    return value.replace("%", "%%")


def render_systemd_unit(project_root: Path, runtime_user: str) -> str:
    """Produce a canonical unit with literal paths and a validated account name.

    ``project_root`` must be absolute. Path existence and account lookup are
    checked separately at deployment time so this interface stays pure.
    """
    project_root = Path(project_root)
    if not project_root.is_absolute():
        raise ValueError("project_root must be an absolute path")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,30}", runtime_user):
        raise ValueError("runtime_user must be a portable Unix account name")

    python = project_root / ".venv" / "bin" / "python"
    return (
        "[Unit]\n"
        "Description=EasyPrent Accounting Webserver\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=exec\n"
        f"User={runtime_user}\n"
        f"WorkingDirectory={_systemd_path(str(project_root))}\n"
        # systemd rejects quotes and backslashes in the *executable* token,
        # even when correctly quoted. env execs the venv Python from argv,
        # where the full quoted path can contain those literal characters.
        f"ExecStart=/usr/bin/env -- {_systemd_string(str(python), command=True)} -m easyprent_accounting.server\n"
        "Restart=on-failure\n"
        "RestartSec=5\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


@dataclass(frozen=True)
class _UnitSnapshot:
    kind: str
    contents: bytes | None = None
    link_target: str | None = None
    mode: int = 0o644


def _snapshot(path: Path) -> _UnitSnapshot:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return _UnitSnapshot("absent")
    if stat.S_ISLNK(info.st_mode):
        return _UnitSnapshot("symlink", link_target=os.readlink(path))
    if stat.S_ISREG(info.st_mode):
        return _UnitSnapshot("file", contents=path.read_bytes(), mode=stat.S_IMODE(info.st_mode))
    raise RuntimeError(f"refusing to replace non-file systemd unit path: {path}")


def _publish(path: Path, contents: bytes, mode: int = 0o644) -> None:
    """Replace a unit file by same-filesystem rename; never follow old links."""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            os.fchmod(handle.fileno(), mode)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _restore(path: Path, snapshot: _UnitSnapshot) -> None:
    if snapshot.kind == "absent":
        path.unlink(missing_ok=True)
    elif snapshot.kind == "file":
        assert snapshot.contents is not None
        _publish(path, snapshot.contents, snapshot.mode)
    elif snapshot.kind == "symlink":
        assert snapshot.link_target is not None
        temporary_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.rollback")
        try:
            temporary_path.symlink_to(snapshot.link_target)
            os.replace(temporary_path, path)
        finally:
            temporary_path.unlink(missing_ok=True)
    else:
        raise AssertionError(f"unknown unit snapshot kind: {snapshot.kind}")


def _checked(run_command: CommandRunner, command: list[str]) -> None:
    status = run_command(command)
    if status != 0:
        raise RuntimeError(f"command failed ({status}): {shlex.join(command)}")


def _status(run_command: CommandRunner, verb: str, name: str) -> bool:
    return run_command(["systemctl", verb, "--quiet", name]) == 0


def _http_health_probe() -> bool:
    """Require this application's HTTP health contract, not just an open port."""
    try:
        # A locally installed proxy must not intercept the loopback probe.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(HEALTH_URL, timeout=0.5) as response:
            if response.status != 200:
                return False
            payload = json.load(response)
    except (OSError, urllib.error.URLError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("status") == "ok" and payload.get("reachable") is True


def _await_stable_health(
    run_command: CommandRunner,
    health_probe: HealthProbe,
    sleep: Sleeper,
) -> None:
    """Observe a live service before making legacy unit retirement permanent."""
    for attempt in range(HEALTH_ATTEMPTS):
        if not _status(run_command, "is-active", CANONICAL_SERVICE_NAME):
            raise RuntimeError("canonical systemd unit did not remain active")
        if health_probe():
            break
        if attempt == HEALTH_ATTEMPTS - 1:
            raise RuntimeError(f"canonical systemd unit failed HTTP health check: {HEALTH_URL}")
        sleep(HEALTH_RETRY_SECONDS)

    sleep(HEALTH_STABILITY_SECONDS)
    if not _status(run_command, "is-active", CANONICAL_SERVICE_NAME):
        raise RuntimeError("canonical systemd unit did not remain active")
    if not health_probe():
        raise RuntimeError(f"canonical systemd unit lost HTTP health: {HEALTH_URL}")


def _probe_runtime_python_access(project_root: Path, python: Path, account: pwd.struct_passwd) -> None:
    """Exercise Python, cwd and SQLite file access as the runtime account.

    The child leaves ``cwd`` and re-enters it after dropping privileges, since
    a privileged parent may otherwise chdir before the child changes user.
    """
    caller_uid = os.geteuid()
    if caller_uid != 0 and caller_uid != account.pw_uid:
        raise ValueError(
            f"root privileges are required to validate runtime user {account.pw_name} "
            f"from caller UID {caller_uid}"
        )

    options: dict[str, object] = {
        "cwd": project_root,
        "capture_output": True,
        "text": True,
        "timeout": 5,
        "check": False,
    }
    if caller_uid == 0:
        options.update(
            user=account.pw_uid,
            group=account.pw_gid,
            extra_groups=os.getgrouplist(account.pw_name, account.pw_gid),
        )
    probe_script = """
import os
import sys
import tempfile

root = sys.argv[1]
try:
    os.chdir('/')
    os.chdir(root)
except OSError as exc:
    sys.exit(f'project root is inaccessible: {exc}')

database = os.path.join(root, 'easyprent_accounting.db')
if os.path.lexists(database):
    try:
        descriptor = os.open(database, os.O_RDWR)
        os.close(descriptor)
    except OSError as exc:
        sys.exit(f'database lacks read/write access: {exc}')

try:
    with tempfile.NamedTemporaryFile(prefix='.easyprent-preflight.', dir=root) as probe:
        probe.write(b'x')
        probe.flush()
        os.fsync(probe.fileno())
except OSError as exc:
    sys.exit(f'cannot create SQLite journal/WAL files in project root: {exc}')
"""
    command = [
        str(python),
        "-I",
        "-c",
        probe_script,
        str(project_root),
    ]
    try:
        completed = subprocess.run(command, **options)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError(
            f"runtime Python cannot execute as {account.pw_name} from {project_root}: {exc}"
        ) from exc
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise ValueError(
            f"runtime Python cannot execute as {account.pw_name} from {project_root} "
            f"(exit {completed.returncode}): {stderr}"
        )


def validate_systemd_unit(
    project_root: Path,
    runtime_user: str,
    *,
    run_command: CommandRunner | None = None,
) -> None:
    """Preflight before package or unit mutation using runtime credentials.

    This creates and removes one probe file in the project root to test SQLite
    journal/WAL permissions, plus a disposable unit under the system temp dir.
    Neither an existing database nor an installed unit is modified.
    """
    project_root = Path(project_root)
    rendered = render_systemd_unit(project_root, runtime_user)
    if not project_root.is_dir():
        raise ValueError(f"project directory does not exist: {project_root}")
    try:
        account = pwd.getpwnam(runtime_user)
    except KeyError as exc:
        raise ValueError(f"runtime user does not exist: {runtime_user}") from exc
    python = project_root / ".venv" / "bin" / "python"
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"runtime Python is not executable: {python}")
    _probe_runtime_python_access(project_root, python, account)
    if run_command is None:
        run_command = _subprocess_runner

    with tempfile.TemporaryDirectory() as verify_directory:
        candidate = Path(verify_directory) / CANONICAL_SERVICE_NAME
        candidate.write_text(rendered, encoding="utf-8")
        _checked(run_command, ["systemd-analyze", "verify", str(candidate)])


def _rollback(
    run_command: CommandRunner,
    canonical_path: Path,
    canonical_snapshot: _UnitSnapshot,
    legacy_path: Path,
    legacy_snapshot: _UnitSnapshot,
    *,
    canonical_active: bool,
    canonical_enabled: bool,
    legacy_active: bool,
    legacy_enabled: bool,
    canonical_published: bool,
    canonical_start_attempted: bool,
) -> list[str]:
    errors: list[str] = []

    def attempt(command: list[str]) -> None:
        try:
            _checked(run_command, command)
        except (OSError, RuntimeError) as exc:
            errors.append(str(exc))

    def safe_status(verb: str, name: str) -> bool:
        try:
            return _status(run_command, verb, name)
        except OSError as exc:
            errors.append(f"checking {name} {verb}: {exc}")
            return False

    # A failed legacy disable or file publication has not changed the running
    # canonical process. Never stop that prior process during such rollback.
    if canonical_published:
        # Stop even a failed/restarting unit once start was attempted, to
        # cancel Restart=on-failure before restoring the old process.
        if canonical_start_attempted or safe_status("is-active", CANONICAL_SERVICE_NAME):
            attempt(["systemctl", "stop", CANONICAL_SERVICE_NAME])
        attempt(["systemctl", "disable", CANONICAL_SERVICE_NAME])
    try:
        if _snapshot(canonical_path) != canonical_snapshot:
            _restore(canonical_path, canonical_snapshot)
        if _snapshot(legacy_path) != legacy_snapshot:
            _restore(legacy_path, legacy_snapshot)
    except OSError as exc:
        errors.append(f"restoring unit files: {exc}")
    attempt(["systemctl", "daemon-reload"])

    if canonical_published and canonical_enabled and canonical_snapshot.kind == "file":
        attempt(["systemctl", "enable", CANONICAL_SERVICE_NAME])
    if legacy_enabled and legacy_snapshot.kind == "file" and not safe_status(
        "is-enabled", LEGACY_SERVICE_NAME
    ):
        attempt(["systemctl", "enable", LEGACY_SERVICE_NAME])
    if canonical_published and canonical_active and canonical_snapshot.kind == "file":
        attempt(["systemctl", "start", CANONICAL_SERVICE_NAME])
    if legacy_active and legacy_snapshot.kind == "file" and not safe_status(
        "is-active", LEGACY_SERVICE_NAME
    ):
        attempt(["systemctl", "start", LEGACY_SERVICE_NAME])
    return errors


def deploy_systemd_unit(
    project_root: Path,
    runtime_user: str,
    *,
    unit_directory: Path = DEFAULT_UNIT_DIRECTORY,
    run_command: CommandRunner | None = None,
    start_if_inactive: bool = True,
    health_probe: HealthProbe | None = None,
    sleep: Sleeper = time.sleep,
) -> None:
    """Validate, publish, activate and remove the legacy unit with rollback.

    ``start_if_inactive`` is true for a new installation. Set it false while
    updating an inactive existing installation; an active old unit is always
    transitioned to the new name. All systemd commands use argv, never a shell.
    """
    project_root = Path(project_root)
    unit_directory = Path(unit_directory)
    if not unit_directory.is_absolute():
        raise ValueError("unit_directory must be an absolute path")
    if not unit_directory.is_dir():
        raise ValueError(f"unit directory does not exist: {unit_directory}")
    if run_command is None:
        run_command = _subprocess_runner
    if health_probe is None:
        health_probe = _http_health_probe
    validate_systemd_unit(project_root, runtime_user, run_command=run_command)
    rendered = render_systemd_unit(project_root, runtime_user)

    canonical_path = unit_directory / CANONICAL_SERVICE_NAME
    legacy_path = unit_directory / LEGACY_SERVICE_NAME
    canonical_snapshot = _snapshot(canonical_path)
    legacy_snapshot = _snapshot(legacy_path)
    if legacy_snapshot.kind == "symlink":
        raise RuntimeError(f"legacy unit is a symlink, not a managed unit: {legacy_path}")
    if canonical_snapshot.kind == "symlink" and canonical_path.resolve() != legacy_path:
        raise RuntimeError(f"canonical unit links outside the managed legacy unit: {canonical_path}")

    legacy_active = _status(run_command, "is-active", LEGACY_SERVICE_NAME)
    legacy_enabled = _status(run_command, "is-enabled", LEGACY_SERVICE_NAME)
    if legacy_active and legacy_snapshot.kind != "file":
        raise RuntimeError("active legacy unit has no file to restore on failure")
    canonical_active = (
        canonical_snapshot.kind == "file"
        and _status(run_command, "is-active", CANONICAL_SERVICE_NAME)
    )
    canonical_enabled = (
        canonical_snapshot.kind == "file"
        and _status(run_command, "is-enabled", CANONICAL_SERVICE_NAME)
    )

    should_enable = start_if_inactive or legacy_enabled or canonical_enabled
    canonical_published = False
    canonical_start_attempted = False
    try:
        # Legacy enablement may own an Alias= symlink at the canonical path.
        # Disable removes links but does not stop the still-running process.
        if legacy_snapshot.kind == "file":
            _checked(run_command, ["systemctl", "disable", LEGACY_SERVICE_NAME])
        _publish(canonical_path, rendered.encode("utf-8"))
        canonical_published = True
        _checked(run_command, ["systemctl", "daemon-reload"])
        if should_enable:
            _checked(run_command, ["systemctl", "enable", CANONICAL_SERVICE_NAME])
        if legacy_active:
            _checked(run_command, ["systemctl", "stop", LEGACY_SERVICE_NAME])
            canonical_start_attempted = True
            _checked(run_command, ["systemctl", "start", CANONICAL_SERVICE_NAME])
        elif canonical_active:
            canonical_start_attempted = True
            _checked(run_command, ["systemctl", "restart", CANONICAL_SERVICE_NAME])
        elif start_if_inactive:
            canonical_start_attempted = True
            _checked(run_command, ["systemctl", "start", CANONICAL_SERVICE_NAME])
        if legacy_active or canonical_active or start_if_inactive:
            _await_stable_health(run_command, health_probe, sleep)

        # The old file stays present during start verification so rollback can
        # still launch the legacy command. Remove it only after stable HTTP health.
        if legacy_snapshot.kind == "file":
            legacy_path.unlink()
            _checked(run_command, ["systemctl", "daemon-reload"])
    except (OSError, RuntimeError) as exc:
        rollback_errors = _rollback(
            run_command,
            canonical_path,
            canonical_snapshot,
            legacy_path,
            legacy_snapshot,
            canonical_active=canonical_active,
            canonical_enabled=canonical_enabled,
            legacy_active=legacy_active,
            legacy_enabled=legacy_enabled,
            canonical_published=canonical_published,
            canonical_start_attempted=canonical_start_attempted,
        )
        details = f"systemd deployment failed: {exc}"
        if rollback_errors:
            details += "; rollback errors: " + "; ".join(rollback_errors)
        raise RuntimeError(details) from exc


def main(argv: list[str] | None = None) -> int:
    """Small CLI for read-only preflight and privileged unit installation."""
    parser = argparse.ArgumentParser(description="Validate or install the canonical EasyPrent systemd unit")
    parser.add_argument("command", choices=("validate", "install"))
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--runtime-user", required=True)
    parser.add_argument("--preserve-inactive", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            if args.preserve_inactive:
                parser.error("--preserve-inactive applies only to install")
            validate_systemd_unit(args.project_root, args.runtime_user)
        else:
            deploy_systemd_unit(
                args.project_root,
                args.runtime_user,
                start_if_inactive=not args.preserve_inactive,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"systemd installation failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

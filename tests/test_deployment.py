from __future__ import annotations

import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from easyprent_accounting import deployment
from easyprent_accounting.deployment import (
    CANONICAL_SERVICE_NAME,
    LEGACY_SERVICE_NAME,
    deploy_systemd_unit,
    render_systemd_unit,
    validate_systemd_unit,
)


class FakeSystemd:
    def __init__(self, unit_directory: Path) -> None:
        self.unit_directory = unit_directory
        self.active = {CANONICAL_SERVICE_NAME: False, LEGACY_SERVICE_NAME: False}
        self.enabled = {CANONICAL_SERVICE_NAME: False, LEGACY_SERVICE_NAME: False}
        self.commands: list[list[str]] = []
        self.fail_verify = False
        self.fail_start_canonical = False
        self.fail_disable_legacy = False
        self.fail_reload_after_legacy_unlink = False

    def __call__(self, command: list[str]) -> int:
        self.commands.append(command)
        if command[:2] == ["systemd-analyze", "verify"]:
            unit_path = Path(command[2])
            if not unit_path.is_file() or "ExecStart=" not in unit_path.read_text(encoding="utf-8"):
                return 1
            return 1 if self.fail_verify else 0

        if command[0] != "systemctl":
            raise AssertionError(f"unexpected command: {command}")
        verb = command[1]
        if verb == "daemon-reload":
            if self.fail_reload_after_legacy_unlink and not (
                self.unit_directory / LEGACY_SERVICE_NAME
            ).exists():
                self.fail_reload_after_legacy_unlink = False
                return 1
            return 0
        if command[2] == "--quiet":
            name = command[3]
        else:
            name = command[2]
        if verb == "is-active":
            return 0 if self.active[name] else 3
        if verb == "is-enabled":
            return 0 if self.enabled[name] else 1
        if verb == "disable":
            if name == LEGACY_SERVICE_NAME and self.fail_disable_legacy:
                return 1
            self.enabled[name] = False
            if name == LEGACY_SERVICE_NAME:
                alias = self.unit_directory / CANONICAL_SERVICE_NAME
                if alias.is_symlink() and alias.resolve() == self.unit_directory / LEGACY_SERVICE_NAME:
                    alias.unlink()
            return 0
        if verb == "enable":
            self.enabled[name] = True
            return 0
        if verb == "stop":
            self.active[name] = False
            return 0
        if verb == "start":
            if name == CANONICAL_SERVICE_NAME and self.fail_start_canonical:
                return 1
            self.active[name] = True
            return 0
        if verb == "restart":
            if name == CANONICAL_SERVICE_NAME and self.fail_start_canonical:
                return 1
            self.active[name] = True
            return 0
        raise AssertionError(f"unexpected command: {command}")


class DeploymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp_dir)
        self.unit_directory = self.root / "units"
        self.unit_directory.mkdir()
        self.project_root = self.root / 'Easy & Prent 20% "Miete" \'Dollar$\\path'
        self.project_root.mkdir()
        python = self.project_root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        self.systemd = FakeSystemd(self.unit_directory)
        self.runtime_user = pwd.getpwuid(os.getuid()).pw_name

    def test_unit_renders_special_path_characters_as_literal_systemd_values(self) -> None:
        unit = render_systemd_unit(self.project_root, "test_user")

        self.assertIn('User=test_user\n', unit)
        self.assertIn(
            f'WorkingDirectory={self.root}/'
            + r'''Easy & Prent 20%% "Miete" 'Dollar$\path'''
            + '\n',
            unit,
        )
        self.assertIn(
            f'ExecStart=/usr/bin/env -- "{self.root}/'
            + r"Easy & Prent 20%% \"Miete\" 'Dollar$$\\path"
            + '/.venv/bin/python" -m easyprent_accounting.server\n',
            unit,
        )
        self.assertNotIn("Alias=", unit)
        self.assertNotIn("easy-prent.service", unit)

    def test_invalid_user_names_are_rejected_before_systemd_commands(self) -> None:
        for runtime_user in ('bad name', 'bad&name', 'bad%name', 'bad"name', "bad'name"):
            with self.subTest(runtime_user=runtime_user):
                with self.assertRaises(ValueError):
                    deploy_systemd_unit(
                        self.project_root,
                        runtime_user,
                        unit_directory=self.unit_directory,
                        run_command=self.systemd,
                    )
                self.assertEqual(self.systemd.commands, [])

    def test_unknown_well_formed_user_is_rejected_before_systemd_commands(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime user does not exist"):
            deploy_systemd_unit(
                self.project_root,
                "no_such_easyprent_user_26703",
                unit_directory=self.unit_directory,
                run_command=self.systemd,
            )
        self.assertEqual(self.systemd.commands, [])

    def test_http_health_probe_uses_direct_loopback_and_application_contract(self) -> None:
        response = mock.MagicMock(status=200)
        response.__enter__.return_value = response
        response.read.return_value = b'{"status":"ok","reachable":true}'
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(
            deployment.urllib.request, "build_opener", return_value=opener
        ) as build_mock:
            self.assertTrue(deployment._http_health_probe())

        self.assertEqual(build_mock.call_args.args[0].proxies, {})
        opener.open.assert_called_once_with(deployment.HEALTH_URL, timeout=0.5)

        response.read.return_value = b'{"status":"ok","reachable":false}'
        with mock.patch.object(deployment.urllib.request, "build_opener", return_value=opener):
            self.assertFalse(deployment._http_health_probe())

    def test_validate_cli_uses_preflight_without_deployment(self) -> None:
        with mock.patch.object(deployment, "validate_systemd_unit") as validate_mock, \
             mock.patch.object(deployment, "deploy_systemd_unit") as deploy_mock:
            status = deployment.main(
                [
                    "validate",
                    "--project-root",
                    str(self.project_root),
                    "--runtime-user",
                    self.runtime_user,
                ]
            )

        self.assertEqual(status, 0)
        validate_mock.assert_called_once_with(self.project_root, self.runtime_user)
        deploy_mock.assert_not_called()

    def test_public_preflight_validates_without_publishing_or_stopping_a_unit(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True

        validate_systemd_unit(
            self.project_root,
            self.runtime_user,
            run_command=self.systemd,
        )

        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertFalse((self.unit_directory / CANONICAL_SERVICE_NAME).exists())
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertEqual(len(self.systemd.commands), 1)
        self.assertEqual(self.systemd.commands[0][:2], ["systemd-analyze", "verify"])

    def test_public_preflight_failure_is_read_only_for_installed_units(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        self.systemd.fail_verify = True

        with self.assertRaises(RuntimeError):
            validate_systemd_unit(
                self.project_root,
                self.runtime_user,
                run_command=self.systemd,
            )

        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertEqual(len(self.systemd.commands), 1)

    def test_preflight_rejects_another_runtime_user_without_root_privileges(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root is authorized to probe another runtime account")

        with self.assertRaisesRegex(ValueError, "root privileges"):
            validate_systemd_unit(
                self.project_root,
                "root",
                run_command=self.systemd,
            )

        self.assertEqual(self.systemd.commands, [])

    def test_runtime_python_access_failure_prevents_any_unit_mutation(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True

        with mock.patch.object(deployment.subprocess, "run", side_effect=PermissionError("access denied")):
            with self.assertRaisesRegex(ValueError, "runtime Python"):
                deploy_systemd_unit(
                    self.project_root,
                    self.runtime_user,
                    unit_directory=self.unit_directory,
                    run_command=self.systemd,
                )

        self.assertEqual(self.systemd.commands, [])
        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])

    def test_root_preflight_runs_python_as_runtime_uid_gid_and_groups(self) -> None:
        account = pwd.getpwnam(self.runtime_user)
        completed = subprocess.CompletedProcess([], 0)
        with mock.patch.object(deployment.os, "geteuid", return_value=0), \
             mock.patch.object(deployment.subprocess, "run", return_value=completed) as run_mock:
            validate_systemd_unit(
                self.project_root,
                self.runtime_user,
                run_command=self.systemd,
            )

        run_mock.assert_called_once()
        args, kwargs = run_mock.call_args
        self.assertEqual(args[0][:3], [str(self.project_root / ".venv/bin/python"), "-I", "-c"])
        self.assertEqual(kwargs["cwd"], self.project_root)
        self.assertEqual(kwargs["user"], account.pw_uid)
        self.assertEqual(kwargs["group"], account.pw_gid)
        self.assertEqual(kwargs["extra_groups"], os.getgrouplist(self.runtime_user, account.pw_gid))

    def test_preflight_rejects_existing_database_without_runtime_write_access(self) -> None:
        database = self.project_root / "easyprent_accounting.db"
        database.write_bytes(b"existing database")
        database.chmod(0o400)

        with self.assertRaisesRegex(ValueError, "database.*read/write"):
            validate_systemd_unit(
                self.project_root,
                self.runtime_user,
                run_command=self.systemd,
            )

        self.assertEqual(database.read_bytes(), b"existing database")
        self.assertEqual(self.systemd.commands, [])

    def test_preflight_rejects_project_root_without_sqlite_journal_creation(self) -> None:
        self.project_root.chmod(0o500)
        try:
            with self.assertRaisesRegex(ValueError, "journal/WAL"):
                validate_systemd_unit(
                    self.project_root,
                    self.runtime_user,
                    run_command=self.systemd,
                )
        finally:
            self.project_root.chmod(0o700)

        self.assertEqual(self.systemd.commands, [])
        self.assertEqual(list(self.project_root.glob(".easyprent-preflight.*")), [])

    def test_fresh_install_publishes_and_starts_only_the_canonical_unit(self) -> None:
        deploy_systemd_unit(
            self.project_root,
            self.runtime_user,
            unit_directory=self.unit_directory,
            run_command=self.systemd,
            health_probe=lambda: True,
            sleep=lambda _: None,
        )

        canonical = self.unit_directory / CANONICAL_SERVICE_NAME
        self.assertTrue(canonical.is_file())
        self.assertFalse(canonical.is_symlink())
        self.assertEqual(canonical.read_text(encoding="utf-8"), render_systemd_unit(self.project_root, self.runtime_user))
        self.assertTrue(self.systemd.active[CANONICAL_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[CANONICAL_SERVICE_NAME])
        self.assertFalse((self.unit_directory / LEGACY_SERVICE_NAME).exists())
        self.assertEqual(self.systemd.commands[0][:2], ["systemd-analyze", "verify"])

    def test_active_legacy_alias_is_replaced_only_after_canonical_validation_and_start(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("[Service]\nExecStart=/old/python -m src.easyprent_accounting.server\n", encoding="utf-8")
        alias = self.unit_directory / CANONICAL_SERVICE_NAME
        alias.symlink_to(legacy)
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True

        deploy_systemd_unit(
            self.project_root,
            self.runtime_user,
            unit_directory=self.unit_directory,
            run_command=self.systemd,
            health_probe=lambda: True,
            sleep=lambda _: None,
        )

        self.assertFalse(legacy.exists())
        self.assertTrue(alias.is_file())
        self.assertFalse(alias.is_symlink())
        self.assertTrue(self.systemd.active[CANONICAL_SERVICE_NAME])
        self.assertFalse(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[CANONICAL_SERVICE_NAME])
        self.assertFalse(self.systemd.enabled[LEGACY_SERVICE_NAME])
        verbs = [command[1] for command in self.systemd.commands if command[0] == "systemctl"]
        self.assertLess(verbs.index("disable"), verbs.index("stop"))
        self.assertLess(verbs.index("stop"), verbs.index("start"))
        self.assertEqual(self.systemd.commands[0][:2], ["systemd-analyze", "verify"])

    def test_legacy_unit_is_retired_only_after_healthy_stable_canonical_service(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        checks: list[bool] = []
        waits: list[float] = []

        def probe() -> bool:
            checks.append(legacy.exists())
            self.assertTrue(self.systemd.active[CANONICAL_SERVICE_NAME])
            return len(checks) >= 3

        deploy_systemd_unit(
            self.project_root,
            self.runtime_user,
            unit_directory=self.unit_directory,
            run_command=self.systemd,
            health_probe=probe,
            sleep=waits.append,
        )

        self.assertEqual(checks, [True, True, True, True])
        self.assertEqual(waits, [0.25, 0.25, 1.0])
        self.assertFalse(legacy.exists())

    def test_unhealthy_canonical_service_rolls_back_active_legacy_alias(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        alias = self.unit_directory / CANONICAL_SERVICE_NAME
        alias.symlink_to(legacy)
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        checks: list[bool] = []

        def probe() -> bool:
            checks.append(legacy.exists())
            return False

        with self.assertRaisesRegex(RuntimeError, "health"):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
                health_probe=probe,
                sleep=lambda _: None,
            )

        self.assertEqual(checks, [True] * 21)
        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertTrue(alias.is_symlink())
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertFalse(self.systemd.active[CANONICAL_SERVICE_NAME])

    def test_crash_during_stability_observation_rolls_back_legacy_unit(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        waits: list[float] = []

        def wait(seconds: float) -> None:
            waits.append(seconds)
            if seconds == 1.0:
                self.systemd.active[CANONICAL_SERVICE_NAME] = False

        with self.assertRaisesRegex(RuntimeError, "active"):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
                health_probe=lambda: True,
                sleep=wait,
            )

        self.assertEqual(waits, [1.0])
        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertFalse(self.systemd.active[CANONICAL_SERVICE_NAME])

    def test_failed_validation_leaves_legacy_alias_and_process_untouched(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("legacy unit", encoding="utf-8")
        alias = self.unit_directory / CANONICAL_SERVICE_NAME
        alias.symlink_to(legacy)
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        self.systemd.fail_verify = True

        with self.assertRaises(RuntimeError):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
            )

        self.assertEqual(legacy.read_text(encoding="utf-8"), "legacy unit")
        self.assertTrue(alias.is_symlink())
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[LEGACY_SERVICE_NAME])
        self.assertEqual(len(self.systemd.commands), 1)

    def test_failed_legacy_disable_does_not_touch_an_existing_canonical_process(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        legacy.write_text("old legacy unit", encoding="utf-8")
        canonical = self.unit_directory / CANONICAL_SERVICE_NAME
        canonical.write_text("old canonical unit", encoding="utf-8")
        self.systemd.active[CANONICAL_SERVICE_NAME] = True
        self.systemd.enabled[CANONICAL_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        self.systemd.fail_disable_legacy = True

        with self.assertRaises(RuntimeError):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
            )

        self.assertEqual(canonical.read_text(encoding="utf-8"), "old canonical unit")
        self.assertEqual(legacy.read_text(encoding="utf-8"), "old legacy unit")
        self.assertTrue(self.systemd.active[CANONICAL_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[CANONICAL_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[LEGACY_SERVICE_NAME])
        self.assertNotIn(["systemctl", "stop", CANONICAL_SERVICE_NAME], self.systemd.commands)
        self.assertNotIn(["systemctl", "disable", CANONICAL_SERVICE_NAME], self.systemd.commands)

    def test_failed_canonical_start_restores_active_enabled_legacy_alias(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        old_unit = "[Service]\nExecStart=/old/python -m src.easyprent_accounting.server\n"
        legacy.write_text(old_unit, encoding="utf-8")
        alias = self.unit_directory / CANONICAL_SERVICE_NAME
        alias.symlink_to(legacy)
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        self.systemd.fail_start_canonical = True

        with self.assertRaises(RuntimeError):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
            )

        self.assertEqual(legacy.read_text(encoding="utf-8"), old_unit)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(), legacy)
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[LEGACY_SERVICE_NAME])
        self.assertFalse(self.systemd.active[CANONICAL_SERVICE_NAME])
        self.assertIn(["systemctl", "stop", CANONICAL_SERVICE_NAME], self.systemd.commands)

    def test_failure_after_legacy_file_deletion_restores_old_unit_and_alias(self) -> None:
        legacy = self.unit_directory / LEGACY_SERVICE_NAME
        old_unit = "[Service]\nExecStart=/old/python -m src.easyprent_accounting.server\n"
        legacy.write_text(old_unit, encoding="utf-8")
        alias = self.unit_directory / CANONICAL_SERVICE_NAME
        alias.symlink_to(legacy)
        self.systemd.active[LEGACY_SERVICE_NAME] = True
        self.systemd.enabled[LEGACY_SERVICE_NAME] = True
        self.systemd.fail_reload_after_legacy_unlink = True

        with self.assertRaises(RuntimeError):
            deploy_systemd_unit(
                self.project_root,
                self.runtime_user,
                unit_directory=self.unit_directory,
                run_command=self.systemd,
                health_probe=lambda: True,
                sleep=lambda _: None,
            )

        self.assertEqual(legacy.read_text(encoding="utf-8"), old_unit)
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(), legacy)
        self.assertTrue(self.systemd.active[LEGACY_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[LEGACY_SERVICE_NAME])
        self.assertFalse(self.systemd.active[CANONICAL_SERVICE_NAME])

    def test_inactive_existing_unit_remains_inactive_during_update(self) -> None:
        canonical = self.unit_directory / CANONICAL_SERVICE_NAME
        canonical.write_text("old canonical unit", encoding="utf-8")
        self.systemd.enabled[CANONICAL_SERVICE_NAME] = True

        deploy_systemd_unit(
            self.project_root,
            self.runtime_user,
            unit_directory=self.unit_directory,
            run_command=self.systemd,
            start_if_inactive=False,
            health_probe=lambda: self.fail("inactive update must not probe HTTP health"),
        )

        self.assertFalse(self.systemd.active[CANONICAL_SERVICE_NAME])
        self.assertTrue(self.systemd.enabled[CANONICAL_SERVICE_NAME])
        self.assertEqual(canonical.read_text(encoding="utf-8"), render_systemd_unit(self.project_root, self.runtime_user))

    @unittest.skipUnless(shutil.which("systemd-analyze"), "systemd-analyze is unavailable")
    def test_rendered_unit_is_accepted_by_systemd_analyze(self) -> None:
        for suffix in ("plain", "space name", "and&name", "percent%name", 'quote"name',
                       "single'name", "dollar$name", "backslash\\name", self.project_root.name):
            with self.subTest(suffix=suffix):
                project = self.root / suffix
                project.mkdir(exist_ok=True)
                python = project / ".venv" / "bin" / "python"
                python.parent.mkdir(parents=True, exist_ok=True)
                if not python.exists():
                    python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                    python.chmod(0o755)
                service = self.root / CANONICAL_SERVICE_NAME
                service.write_text(render_systemd_unit(project, self.runtime_user), encoding="utf-8")
                completed = subprocess.run(
                    ["systemd-analyze", "verify", str(service)],
                    capture_output=True,
                    text=True,
                )
                sandbox_socket_errors = (
                    "Failed to turn off SO_PASSRIGHTS on user lookup socket, ignoring: Operation not permitted",
                    "Failed to enable SO_PASSCRED on handoff timestamp socket: Operation not permitted",
                )
                if completed.returncode != 0 and tuple(completed.stderr.splitlines()) == sandbox_socket_errors:
                    self.skipTest("systemd-analyze cannot open credential sockets in this sandbox")
                self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()

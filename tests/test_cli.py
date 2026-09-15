from __future__ import annotations

from contextlib import chdir
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from easyprent_accounting import cli
from easyprent_accounting.config import get_global_config, load_config
from tests.support import mocked_global_config


class EasyPrentCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.project_root = Path(self.temp_dir)
        self.runtime_dir = self.project_root / ".easyprent"
        self.pid_file = self.runtime_dir / "server.pid"
        self.log_file = self.runtime_dir / "server.log"

        (self.project_root / "easyprent_accounting").mkdir(parents=True)

        self.enterContext(mocked_global_config(load_config({"EASYPRENT_PROJECT_ROOT": str(self.project_root)})))

    def _create_fake_venv(self) -> Path:
        python = self.project_root / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.touch()
        return python

    def _fake_systemd_unit(self, project_root: Path | None = None) -> Path:
        unit = self.project_root / "easy-prent.service"
        unit.write_text(
            f"[Service]\nUser=root\nWorkingDirectory={project_root or self.project_root}\n",
            encoding="utf-8",
        )
        return unit

    def _run_start_server(self, pid: int) -> tuple[int, mock.Mock]:
        process = mock.Mock(pid=pid)
        process.poll.return_value = None

        with mock.patch.object(cli, "running_pid", return_value=None), mock.patch.object(
            cli, "server_command", return_value=["python3", "-m", "easyprent_accounting.server"]
        ), mock.patch.object(cli.subprocess, "Popen", return_value=process) as popen_mock, mock.patch.object(
            cli.time, "sleep"
        ):
            exit_code = cli.start_server({})

        return exit_code, popen_mock

    def _assert_server_started_in_project_root(self, popen_mock: mock.Mock) -> None:
        popen_mock.assert_called_once()
        self.assertEqual(popen_mock.call_args.kwargs["cwd"], self.project_root.resolve())
        self.assertEqual(
            popen_mock.call_args.kwargs["env"]["EASYPRENT_DB_PATH"],
            str((self.project_root / "easyprent_accounting.db").resolve()),
        )

    def test_start_server_launches_background_process_and_writes_pid(self) -> None:
        exit_code, popen_mock = self._run_start_server(4321)

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.pid_file.read_text(encoding="utf-8").strip(), "4321")
        self._assert_server_started_in_project_root(popen_mock)

    def test_start_server_from_other_working_directory_preserves_project_root_database(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir:
            other_path = Path(other_dir).resolve()
            with mock.patch("pathlib.Path.cwd", return_value=other_path):
                exit_code, popen_mock = self._run_start_server(5678)

            self.assertEqual(exit_code, 0)
            self._assert_server_started_in_project_root(popen_mock)

    def test_main_without_root_env_uses_checkout_from_foreign_cwd(self) -> None:
        checkout_path = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as foreign_dir, \
             chdir(foreign_dir), \
             mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch.object(cli, "start_server", return_value=0) as start_mock:
            exit_code = cli.main(["start"])
            cfg = get_global_config()

        self.assertEqual(exit_code, 0)
        self.assertEqual(cfg.project_root, checkout_path)
        self.assertEqual(
            cfg.db_path,
            (checkout_path / "easyprent_accounting.db").resolve(),
        )
        start_mock.assert_called_once_with({})


    def test_stop_server_removes_stale_pid_file(self) -> None:
        self.runtime_dir.mkdir()
        self.pid_file.write_text("9999\n", encoding="utf-8")

        with mock.patch.object(cli, "is_running", return_value=False):
            exit_code = cli.stop_server()

        self.assertEqual(exit_code, 0)
        self.assertFalse(self.pid_file.exists())

    def test_update_reenters_fresh_cli_after_pull(self) -> None:
        venv_python = self._create_fake_venv()
        completed = mock.Mock(returncode=0, stdout=str(self.project_root))
        with mock.patch.object(cli, "run_command", return_value=0) as run_command_mock, mock.patch.object(
            cli.subprocess, "run", return_value=completed
        ):
            exit_code = cli.update_project({})

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            run_command_mock.call_args_list,
            [
                mock.call(["git", "pull", "--ff-only"]),
                mock.call(
                    [
                        str(venv_python),
                        "-m",
                        "easyprent_accounting.cli",
                        "finish-update",
                    ]
                ),
            ],
        )

    def test_update_does_not_require_node_at_runtime(self) -> None:
        (self.project_root / "package.json").write_text("{}", encoding="utf-8")
        (self.project_root / "package-lock.json").write_text("{}", encoding="utf-8")
        completed = mock.Mock(returncode=0, stdout=str(self.project_root))
        with mock.patch.object(
            cli, "run_command", return_value=0
        ) as run_command_mock, mock.patch.object(
            cli.subprocess, "run", return_value=completed
        ):
            exit_code = cli.update_project({})

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_command_mock.call_count, 2)
        self.assertEqual(run_command_mock.call_args_list[0], mock.call(["git", "pull", "--ff-only"]))
        self.assertNotIn("npm", repr(run_command_mock.call_args_list))

    def test_update_propagates_fresh_cli_failure(self) -> None:
        completed = mock.Mock(returncode=0, stdout=str(self.project_root))
        with mock.patch.object(cli, "run_command", side_effect=[0, 1]) as run_command_mock, \
             mock.patch.object(cli.subprocess, "run", return_value=completed):
            exit_code = cli.update_project({})

        self.assertEqual(exit_code, 1)
        self.assertEqual(run_command_mock.call_count, 2)

    def test_root_update_runs_git_as_checkout_owner(self) -> None:
        completed = mock.Mock(returncode=0)
        owner_uid = self.project_root.stat().st_uid
        with mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli.subprocess, "run", return_value=completed) as run_mock:
            status = cli._run_as_checkout_owner(
                ["git", "pull", "--ff-only"], self.project_root
            )

        self.assertEqual(status, 0)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0], ["git", "pull", "--ff-only"])
        self.assertEqual(run_mock.call_args.kwargs["user"], owner_uid)
        self.assertEqual(run_mock.call_args.kwargs["cwd"], self.project_root)
        self.assertNotEqual(run_mock.call_args.kwargs["env"]["HOME"], "/root")

    def test_update_git_preflight_trusts_only_this_checkout_under_sudo(self) -> None:
        completed = mock.Mock(returncode=0, stdout=str(self.project_root))
        with mock.patch.object(cli.subprocess, "run", return_value=completed) as run_mock, \
             mock.patch.object(cli, "run_command", return_value=0):
            self.assertEqual(cli.update_project({}), 0)

        self.assertEqual(
            run_mock.call_args.args[0],
            [
                "git",
                "-c",
                f"safe.directory={self.project_root.resolve()}",
                "rev-parse",
                "--show-toplevel",
            ],
        )
        self.assertEqual(run_mock.call_args.kwargs["cwd"], self.project_root)

    def test_update_rejects_git_parent_checkout_without_pulling(self) -> None:
        completed = mock.Mock(returncode=0, stdout=str(self.project_root.parent))
        with mock.patch.object(cli.subprocess, "run", return_value=completed), \
             mock.patch.object(cli, "run_command") as run_mock:
            self.assertEqual(cli.update_project({}), 1)

        run_mock.assert_not_called()

    def test_root_install_and_retirement_use_owner_module_commands(self) -> None:
        venv_python = self._create_fake_venv()
        with mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli, "_run_as_checkout_owner", return_value=0) as owner_run:
            cli._install_as_checkout_owner(self.project_root, venv_python)
            cli._retire_as_checkout_owner(self.project_root, venv_python)

        self.assertEqual(
            owner_run.call_args_list,
            [
                mock.call(
                    [
                        str(venv_python),
                        "-m",
                        "easyprent_accounting.packaging",
                        "install",
                        str(self.project_root),
                    ],
                    self.project_root,
                ),
                mock.call(
                    [
                        str(venv_python),
                        "-m",
                        "easyprent_accounting.packaging",
                        "retire-legacy",
                    ],
                    self.project_root,
                ),
            ],
        )

    def test_finish_update_installs_then_retires_legacy_before_direct_restart(self) -> None:
        venv_python = self._create_fake_venv()
        order = mock.Mock()
        order.restart.return_value = 0
        with mock.patch.object(cli, "running_pid", return_value=1234), \
             mock.patch.object(cli, "installed_systemd_unit", return_value=None), \
             mock.patch.object(cli, "_install_as_checkout_owner", order.install), \
             mock.patch.object(cli, "_retire_as_checkout_owner", order.retire), \
             mock.patch.object(cli, "restart_server", order.restart):
            exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            order.mock_calls,
            [
                mock.call.install(self.project_root, venv_python),
                mock.call.retire(self.project_root, venv_python),
                mock.call.restart({}),
            ],
        )

    def test_finish_update_migrates_systemd_before_retiring_legacy(self) -> None:
        venv_python = self._create_fake_venv()
        unit = self._fake_systemd_unit()
        order = mock.Mock()
        with mock.patch.object(cli, "running_pid", return_value=None), \
             mock.patch.object(cli, "installed_systemd_unit", return_value=unit), \
             mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli, "systemd_unit_is_active", return_value=True), \
             mock.patch.object(cli, "validate_systemd_unit", order.validate), \
             mock.patch.object(cli, "_install_as_checkout_owner", order.install), \
             mock.patch.object(cli, "deploy_systemd_unit", order.deploy), \
             mock.patch.object(cli, "_retire_as_checkout_owner", order.retire), \
             mock.patch.object(cli, "restart_server", order.restart):
            exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            order.mock_calls,
            [
                mock.call.validate(self.project_root, "root"),
                mock.call.install(self.project_root, venv_python),
                mock.call.deploy(self.project_root, "root", start_if_inactive=False),
                mock.call.retire(self.project_root, venv_python),
            ],
        )

    def test_finish_update_keeps_legacy_when_systemd_deployment_fails(self) -> None:
        self._create_fake_venv()
        unit = self._fake_systemd_unit()
        with mock.patch.object(cli, "running_pid", return_value=None), \
             mock.patch.object(cli, "installed_systemd_unit", return_value=unit), \
             mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli, "systemd_unit_is_active", return_value=True), \
             mock.patch.object(cli, "validate_systemd_unit"), \
             mock.patch.object(cli, "_install_as_checkout_owner"), \
             mock.patch.object(cli, "deploy_systemd_unit", side_effect=RuntimeError("unit failed")), \
             mock.patch.object(cli, "_retire_as_checkout_owner") as retire_mock:
            exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 1)
        retire_mock.assert_not_called()

    def test_finish_update_preflight_failure_does_not_mutate_python(self) -> None:
        self._create_fake_venv()
        unit = self._fake_systemd_unit()
        with mock.patch.object(cli, "running_pid", return_value=None), \
             mock.patch.object(cli, "installed_systemd_unit", return_value=unit), \
             mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli, "systemd_unit_is_active", return_value=True), \
             mock.patch.object(cli, "validate_systemd_unit", side_effect=RuntimeError("bad unit")), \
             mock.patch.object(cli, "_install_as_checkout_owner") as install_mock, \
             mock.patch.object(cli, "_retire_as_checkout_owner") as retire_mock:
            exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 1)
        install_mock.assert_not_called()
        retire_mock.assert_not_called()

    def test_finish_update_rejects_unit_owned_by_another_checkout(self) -> None:
        self._create_fake_venv()
        with tempfile.TemporaryDirectory() as other_dir:
            unit = self._fake_systemd_unit(Path(other_dir))
            with mock.patch.object(cli, "running_pid", return_value=None), \
                 mock.patch.object(cli, "installed_systemd_unit", return_value=unit), \
                 mock.patch.object(cli.os, "geteuid", return_value=0), \
                 mock.patch.object(cli, "_install_as_checkout_owner") as install_mock, \
                 mock.patch.object(cli, "deploy_systemd_unit") as deploy_mock:
                exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 1)
        install_mock.assert_not_called()
        deploy_mock.assert_not_called()

    def test_finish_update_restarts_direct_server_with_inactive_unit(self) -> None:
        venv_python = self._create_fake_venv()
        unit = self._fake_systemd_unit()
        order = mock.Mock()
        order.restart.return_value = 0
        with mock.patch.object(cli, "running_pid", return_value=1234), \
             mock.patch.object(cli, "installed_systemd_unit", return_value=unit), \
             mock.patch.object(cli.os, "geteuid", return_value=0), \
             mock.patch.object(cli, "systemd_unit_is_active", return_value=False), \
             mock.patch.object(cli, "validate_systemd_unit", order.validate), \
             mock.patch.object(cli, "_install_as_checkout_owner", order.install), \
             mock.patch.object(cli, "deploy_systemd_unit", order.deploy), \
             mock.patch.object(cli, "_retire_as_checkout_owner", order.retire), \
             mock.patch.object(cli, "restart_server", order.restart):
            exit_code = cli.finish_update({})

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            order.mock_calls,
            [
                mock.call.validate(self.project_root, "root"),
                mock.call.install(self.project_root, venv_python),
                mock.call.deploy(self.project_root, "root", start_if_inactive=False),
                mock.call.retire(self.project_root, venv_python),
                mock.call.restart({}),
            ],
        )

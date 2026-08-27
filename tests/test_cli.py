from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.easyprent_accounting import cli


class EasyPrentCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temp_dir.name)
        self.runtime_dir = self.project_root / ".easyprent"
        self.pid_file = self.runtime_dir / "server.pid"
        self.log_file = self.runtime_dir / "server.log"
        self.original_cwd = Path.cwd()
        self.cwd_patch = mock.patch("src.easyprent_accounting.cli.Path.cwd", return_value=self.project_root)

        (self.project_root / "src" / "easyprent_accounting").mkdir(parents=True)
        self.cwd_patch.start()

    def tearDown(self) -> None:
        self.cwd_patch.stop()
        self.temp_dir.cleanup()

    def test_start_server_launches_background_process_and_writes_pid(self) -> None:
        process = mock.Mock(pid=4321)
        process.poll.return_value = None

        with mock.patch.object(cli, "running_pid", return_value=None), mock.patch.object(
            cli, "server_command", return_value=["python3", "-m", "src.easyprent_accounting.server"]
        ), mock.patch.object(cli.subprocess, "Popen", return_value=process) as popen_mock, mock.patch.object(
            cli.time, "sleep"
        ):
            exit_code = cli.start_server()

        self.assertEqual(exit_code, 0)
        self.assertEqual(self.pid_file.read_text(encoding="utf-8").strip(), "4321")
        popen_mock.assert_called_once()

    def test_stop_server_removes_stale_pid_file(self) -> None:
        self.runtime_dir.mkdir()
        self.pid_file.write_text("9999\n", encoding="utf-8")

        with mock.patch.object(cli, "is_running", return_value=False):
            exit_code = cli.stop_server()

        self.assertEqual(exit_code, 0)
        self.assertFalse(self.pid_file.exists())

    def test_update_runs_pull_and_restarts_running_server(self) -> None:
        (self.project_root / "package.json").write_text("{}", encoding="utf-8")
        (self.project_root / "package-lock.json").write_text("{}", encoding="utf-8")

        completed = mock.Mock(returncode=0)
        with mock.patch.object(cli, "running_pid", return_value=1111), mock.patch.object(
            cli, "restart_server", return_value=0
        ) as restart_mock, mock.patch.object(cli, "run_command", return_value=0) as run_command_mock, mock.patch.object(
            cli.subprocess, "run", return_value=completed
        ), mock.patch.object(
            cli, "systemd_service_is_running", return_value=False
        ):
            exit_code = cli.update_project()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            run_command_mock.call_args_list,
            [mock.call(["git", "pull", "--ff-only"]), mock.call(["npm", "install"])],
        )
        restart_mock.assert_called_once_with()

    def test_update_skips_npm_when_it_is_not_installed(self) -> None:
        (self.project_root / "package.json").write_text("{}", encoding="utf-8")
        (self.project_root / "package-lock.json").write_text("{}", encoding="utf-8")

        completed = mock.Mock(returncode=0)
        with mock.patch.object(cli, "running_pid", return_value=False), mock.patch.object(
            cli, "run_command", return_value=0
        ) as run_command_mock, mock.patch("shutil.which", return_value=None), mock.patch.object(
            cli.subprocess, "run", return_value=completed
        ), mock.patch.object(
            cli, "systemd_service_is_running", return_value=False
        ):
            exit_code = cli.update_project()

        self.assertEqual(exit_code, 0)
        run_command_mock.assert_called_once_with(["git", "pull", "--ff-only"])

    def test_update_restarts_active_systemd_service(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch.object(cli, "running_pid", return_value=None), mock.patch.object(
            cli, "systemd_service_is_running", return_value=True
        ), mock.patch.object(cli, "restart_server") as restart_mock, mock.patch.object(
            cli, "run_command", return_value=0
        ) as run_command_mock, mock.patch.object(cli.subprocess, "run", return_value=completed):
            exit_code = cli.update_project()

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            run_command_mock.call_args_list,
            [
                mock.call(["git", "pull", "--ff-only"]),
                mock.call(["systemctl", "restart", "easy-prent.service"]),
            ],
        )
        restart_mock.assert_not_called()

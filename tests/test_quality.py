from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import quality


class QualityScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = self.enterContext(tempfile.TemporaryDirectory())
        self.project_root = Path(self.temp_dir)
        self.project_root_patch = mock.patch.object(
            quality,
            "PROJECT_ROOT",
            self.project_root,
        )
        self.project_root_patch.start()
        self.addCleanup(self.project_root_patch.stop)

    def _write_node_manifests(self, *, package_json: bool = True, package_lock: bool = True) -> None:
        if package_json:
            (self.project_root / "package.json").write_text("{}\n", encoding="utf-8")
        if package_lock:
            (self.project_root / "package-lock.json").write_text("{}\n", encoding="utf-8")
        (self.project_root / "src" / "api").mkdir(parents=True, exist_ok=True)
        (self.project_root / "openapi.json").write_text("{}\n", encoding="utf-8")
        (self.project_root / "src" / "api" / "schema.d.ts").write_text("// generated\n", encoding="utf-8")

    def _which(self, executable: str) -> str | None:
        return {
            "node": "/test/bin/node",
            "npm": "/test/bin/npm",
        }.get(executable)

    def test_node_and_npm_are_required(self) -> None:
        self._write_node_manifests()

        for missing_tool in ("node", "npm"):
            with self.subTest(missing_tool=missing_tool), mock.patch.object(
                quality.shutil,
                "which",
                side_effect=lambda executable, missing=missing_tool: (
                    None if executable == missing else self._which(executable)
                ),
            ), mock.patch.object(quality, "run") as run_mock:
                with mock.patch.object(quality.sys, "stderr", io.StringIO()):
                    self.assertEqual(quality.main(), 1)
                run_mock.assert_not_called()

    def test_package_json_and_lockfile_are_required_as_a_pair(self) -> None:
        for package_json, package_lock in ((False, False), (True, False), (False, True)):
            with self.subTest(package_json=package_json, package_lock=package_lock):
                for manifest in ("package.json", "package-lock.json"):
                    (self.project_root / manifest).unlink(missing_ok=True)
                self._write_node_manifests(
                    package_json=package_json,
                    package_lock=package_lock,
                )

                with mock.patch.object(
                    quality.shutil,
                    "which",
                    side_effect=self._which,
                ), mock.patch.object(quality, "run") as run_mock:
                    with mock.patch.object(quality.sys, "stderr", io.StringIO()):
                        self.assertEqual(quality.main(), 1)
                    run_mock.assert_not_called()

    def test_quality_installs_locked_dependencies_before_other_checks(self) -> None:
        self._write_node_manifests()

        with mock.patch.object(
            quality.shutil,
            "which",
            side_effect=self._which,
        ), mock.patch.object(quality, "run") as run_mock:
            self.assertEqual(quality.main(), 0)

        self.assertEqual(
            run_mock.call_args_list,
            [
                mock.call(["/test/bin/npm", "ci", "--ignore-scripts"]),
                mock.call(["/test/bin/npm", "run", "typecheck"]),
                mock.call(["/test/bin/npm", "run", "test"]),
                mock.call(["/test/bin/npm", "run", "build"]),
                mock.call([quality.sys.executable, "scripts/export_openapi.py"]),
                mock.call(["/test/bin/npm", "run", "generate-api"]),
                mock.call([quality.sys.executable, "-m", "unittest", "discover", "-s", "tests"]),
                mock.call([quality.sys.executable, "-c", "import " + ", ".join(quality.PACKAGE_IMPORTS)]),
            ],
        )

    def test_changed_generated_contract_stops_before_python_tests(self) -> None:
        self._write_node_manifests()

        def run_with_stale_output(command: list[str]) -> None:
            if command[-1] == "generate-api":
                (self.project_root / "src" / "api" / "schema.d.ts").write_text(
                    "// stale\n", encoding="utf-8"
                )

        with mock.patch.object(
            quality.shutil, "which", side_effect=self._which
        ), mock.patch.object(quality, "run", side_effect=run_with_stale_output) as run_mock:
            with mock.patch.object(quality.sys, "stderr", io.StringIO()):
                self.assertEqual(quality.main(), 1)

        self.assertEqual(run_mock.call_count, 6)

    def test_npm_failure_stops_quality_checks(self) -> None:
        self._write_node_manifests()
        failure = subprocess.CalledProcessError(1, ["npm", "ci"])

        with mock.patch.object(
            quality.shutil,
            "which",
            side_effect=self._which,
        ), mock.patch.object(quality, "run", side_effect=failure) as run_mock:
            with self.assertRaises(subprocess.CalledProcessError):
                quality.main()

        run_mock.assert_called_once_with(["/test/bin/npm", "ci", "--ignore-scripts"])


if __name__ == "__main__":
    unittest.main()

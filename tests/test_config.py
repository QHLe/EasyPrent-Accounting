from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from easyprent_accounting.config import (
    AppConfig,
    SenderAddress,
    get_global_config,
    load_config,
    set_global_config,
)
from tests.support import preserved_global_config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(preserved_global_config())

    def _make_checkout(self, project_root: Path, *, project_name: str = "easyprent-accounting") -> None:
        (project_root / "pyproject.toml").write_text(
            f'[project]\nname = "{project_name}"\n',
            encoding="utf-8",
        )
        package = project_root / "easyprent_accounting"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "config.py").write_text("", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=project_root, check=True)
        subprocess.run(
            ["git", "add", "pyproject.toml", "easyprent_accounting/__init__.py", "easyprent_accounting/config.py"],
            cwd=project_root,
            check=True,
        )

    def test_load_config_expands_user_paths(self) -> None:
        cfg = load_config({
            "EASYPRENT_SETTLEMENT_TEMPLATE": "~/custom_template.ods",
            "EASYPRENT_PROJECT_ROOT": "~/my_project",
            "EASYPRENT_DB_PATH": "~/my_db.db",
        })
        self.assertEqual(cfg.settlement_template, (Path.home() / "custom_template.ods").resolve())
        self.assertEqual(cfg.project_root, (Path.home() / "my_project").resolve())
        self.assertEqual(cfg.db_path, (Path.home() / "my_db.db").resolve())

    def test_load_config_defaults_db_to_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})
            self.assertEqual(cfg.db_path, (project_root / "easyprent_accounting.db").resolve())

    def test_load_config_defaults_to_checkout_when_cwd_is_foreign(self) -> None:
        checkout_path = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as foreign_dir:
            foreign_path = Path(foreign_dir).resolve()
            with mock.patch("pathlib.Path.cwd", return_value=foreign_path):
                cfg = load_config({})

        self.assertEqual(cfg.project_root, checkout_path)
        self.assertEqual(
            cfg.db_path,
            (checkout_path / "easyprent_accounting.db").resolve(),
        )
        self.assertEqual(
            cfg.settlement_template,
            (checkout_path / "templates" / "utility_settlement.ods").resolve(),
        )

    def test_load_config_defaults_to_cwd_outside_checkout(self) -> None:
        source_package = (
            Path(__file__).resolve().parents[1] / "easyprent_accounting"
        )
        with (
            tempfile.TemporaryDirectory() as site_dir,
            tempfile.TemporaryDirectory() as foreign_dir,
        ):
            copied_package = Path(site_dir) / "easyprent_accounting"
            copied_package.mkdir()
            shutil.copy2(
                source_package / "__init__.py",
                copied_package / "__init__.py",
            )
            shutil.copy2(source_package / "config.py", copied_package / "config.py")

            marker_root = Path(foreign_dir).resolve()
            foreign_path = marker_root / "working"
            foreign_path.mkdir()
            template_path = marker_root / "templates" / "utility_settlement.ods"
            template_path.parent.mkdir()
            template_path.write_bytes(b"not a checkout template")
            (marker_root / "pyproject.toml").write_text(
                '[project]\nname = "easyprent-accounting"\n',
                encoding="utf-8",
            )
            foreign_package = marker_root / "easyprent_accounting"
            foreign_package.mkdir()
            (foreign_package / "__init__.py").write_text("", encoding="utf-8")

            script = """
from pathlib import Path
from easyprent_accounting.config import load_config

config = load_config({})
assert config.project_root == Path.cwd().resolve()
assert config.db_path == (Path.cwd() / "easyprent_accounting.db").resolve()
assert config.settlement_template is None
"""
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=foreign_path,
                env={"PYTHONPATH": site_dir, "PYTHONNOUSERSITE": "1"},
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_get_global_config_raises_when_uninitialized(self) -> None:
        set_global_config(None)
        with self.assertRaises(RuntimeError) as ctx:
            get_global_config()
        self.assertIn("AppConfig not initialised", str(ctx.exception))

    def test_set_and_get_global_config(self) -> None:
        cfg = AppConfig(
            db_path=Path("/tmp/test.db"),
            project_root=Path("/tmp"),
            sender=SenderAddress(name="Sender", street="Street 1", city="City"),
            settlement_template=None,
        )
        set_global_config(cfg)
        self.assertEqual(get_global_config(), cfg)
        self.assertEqual(cfg.sender.name, "Sender")
        self.assertEqual(cfg.sender.street, "Street 1")
        self.assertEqual(cfg.sender.city, "City")

    def test_load_config_resolves_relative_settlement_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            cfg = load_config({
                "EASYPRENT_PROJECT_ROOT": str(project_root),
                "EASYPRENT_SETTLEMENT_TEMPLATE": "relative/template.ods",
            })
            self.assertEqual(cfg.settlement_template, (project_root / "relative/template.ods").resolve())

    def test_load_config_resolves_checkout_template_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            self._make_checkout(project_root)
            template_file = project_root / "templates" / "utility_settlement.ods"
            template_file.parent.mkdir(parents=True)
            template_file.write_bytes(b"dummy ods")

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})
            self.assertEqual(cfg.settlement_template, template_file.resolve())

    def test_load_config_sets_none_template_when_checkout_file_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            self._make_checkout(project_root)
            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})
            self.assertIsNone(cfg.settlement_template)

    def test_load_config_ignores_template_from_wrong_project_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            self._make_checkout(project_root, project_name="other-accounting")
            template_file = project_root / "templates" / "utility_settlement.ods"
            template_file.parent.mkdir(parents=True)
            template_file.write_bytes(b"not this project's template")

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})

            self.assertEqual(cfg.project_root, project_root.resolve())
            self.assertIsNone(cfg.settlement_template)

    def test_load_config_ignores_template_from_untracked_marker_git_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "pyproject.toml").write_text(
                '[project]\nname = "easyprent-accounting"\n', encoding="utf-8"
            )
            package = project_root / "easyprent_accounting"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "config.py").write_text("", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=project_root, check=True)
            template_file = project_root / "templates" / "utility_settlement.ods"
            template_file.parent.mkdir(parents=True)
            template_file.write_bytes(b"not a tracked checkout")

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})

            self.assertIsNone(cfg.settlement_template)

    def test_load_config_ignores_template_from_unverified_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            template_file = project_root / "templates" / "utility_settlement.ods"
            template_file.parent.mkdir(parents=True)
            template_file.write_bytes(b"not from a checkout")

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})

            self.assertIsNone(cfg.settlement_template)

    def test_load_config_bundles_sender_address(self) -> None:
        cfg = load_config({
            "EASYPRENT_SENDER_NAME": "Hausverwaltung Meyer",
            "EASYPRENT_SENDER_STREET": "Hauptstr. 10",
            "EASYPRENT_SENDER_CITY": "10115 Berlin",
        })
        self.assertEqual(
            cfg.sender,
            SenderAddress(
                name="Hausverwaltung Meyer",
                street="Hauptstr. 10",
                city="10115 Berlin",
            ),
        )

    def test_global_config_project_root_remains_stable_after_cwd_change(self) -> None:
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            path_a = Path(dir_a).resolve()
            path_b = Path(dir_b).resolve()

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(path_a)})
            set_global_config(cfg)
            self.assertEqual(get_global_config().project_root, path_a)

            with mock.patch("pathlib.Path.cwd", return_value=path_b):
                self.assertEqual(get_global_config().project_root, path_a)


if __name__ == "__main__":
    unittest.main()

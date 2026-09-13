from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from easyprent_accounting.config import (
    AppConfig,
    SenderAddress,
    get_global_config,
    load_config,
    resolve_project_root,
    set_global_config,
)
from tests.support import preserved_global_config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(preserved_global_config())

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

    def test_load_config_defaults_db_to_cwd_when_no_root_or_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd_path = Path(temp_dir).resolve()
            with mock.patch("pathlib.Path.cwd", return_value=cwd_path), \
                 mock.patch("easyprent_accounting.config.find_checkout_root", return_value=None):
                cfg = load_config({})
                self.assertEqual(cfg.db_path, (cwd_path / "easyprent_accounting.db").resolve())

    def test_resolve_project_root_prefers_override_then_checkout_then_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir).resolve()
            # 1. Override takes precedence
            self.assertEqual(resolve_project_root(target), target)

            # 2. Checkout root is second precedence
            with mock.patch("easyprent_accounting.config.find_checkout_root", return_value=target):
                self.assertEqual(resolve_project_root(None), target)

            # 3. CWD is third precedence
            with mock.patch("easyprent_accounting.config.find_checkout_root", return_value=None), \
                 mock.patch("pathlib.Path.cwd", return_value=target):
                self.assertEqual(resolve_project_root(None), target)

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
        self.assertEqual(cfg.sender_name, "Sender")
        self.assertEqual(cfg.sender_street, "Street 1")
        self.assertEqual(cfg.sender_city, "City")

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
            template_file = project_root / "templates" / "utility_settlement.ods"
            template_file.parent.mkdir(parents=True)
            template_file.write_bytes(b"dummy ods")

            cfg = load_config({"EASYPRENT_PROJECT_ROOT": str(project_root)})
            self.assertEqual(cfg.settlement_template, template_file.resolve())

    def test_load_config_sets_none_template_when_checkout_file_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
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
            SenderAddress(name="Hausverwaltung Meyer", street="Hauptstr. 10", city="10115 Berlin"),
        )
        self.assertEqual(cfg.sender_name, "Hausverwaltung Meyer")
        self.assertEqual(cfg.sender_street, "Hauptstr. 10")
        self.assertEqual(cfg.sender_city, "10115 Berlin")

    def test_load_config_defaults_db_and_root_to_checkout_when_cwd_is_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as checkout_dir, tempfile.TemporaryDirectory() as foreign_dir:
            checkout_path = Path(checkout_dir).resolve()
            (checkout_path / "pyproject.toml").touch()
            foreign_path = Path(foreign_dir).resolve()

            with mock.patch("pathlib.Path.cwd", return_value=foreign_path), \
                 mock.patch("easyprent_accounting.config.find_checkout_root", return_value=checkout_path):
                cfg = load_config({})
                self.assertEqual(cfg.project_root, checkout_path)
                self.assertEqual(cfg.db_path, (checkout_path / "easyprent_accounting.db").resolve())

    def test_global_config_project_root_remains_stable_after_cwd_change(self) -> None:
        with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
            path_a = Path(dir_a).resolve()
            path_b = Path(dir_b).resolve()

            with mock.patch("pathlib.Path.cwd", return_value=path_a), \
                 mock.patch("easyprent_accounting.config.find_checkout_root", return_value=None):
                cfg = load_config({})
                set_global_config(cfg)
                self.assertEqual(get_global_config().project_root, path_a)

            with mock.patch("pathlib.Path.cwd", return_value=path_b):
                self.assertEqual(get_global_config().project_root, path_a)


if __name__ == "__main__":
    unittest.main()

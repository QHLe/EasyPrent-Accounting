from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from easyprent_accounting.config import (
    AppConfig,
    get_global_config,
    get_project_root,
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
            sender_name="Sender",
            sender_street="Street 1",
            sender_city="City",
            settlement_template=None,
        )
        set_global_config(cfg)
        self.assertEqual(get_global_config(), cfg)

    def test_load_config_resolves_relative_settlement_template(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            cfg = load_config({
                "EASYPRENT_PROJECT_ROOT": str(project_root),
                "EASYPRENT_SETTLEMENT_TEMPLATE": "relative/template.ods",
            })
            self.assertEqual(cfg.settlement_template, (project_root / "relative/template.ods").resolve())

    def test_get_project_root_delegates_to_global_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir).resolve()
            set_global_config(
                AppConfig(
                    db_path=project_root / "easyprent_accounting.db",
                    project_root=project_root,
                    sender_name=None,
                    sender_street=None,
                    sender_city=None,
                    settlement_template=None,
                )
            )
            self.assertEqual(get_project_root(), project_root)



if __name__ == "__main__":
    unittest.main()


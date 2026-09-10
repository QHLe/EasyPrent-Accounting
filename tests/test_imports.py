from __future__ import annotations

import importlib
import pkgutil
import unittest

import easyprent_accounting


class ImportSmokeTest(unittest.TestCase):
    def test_all_modules_are_importable(self) -> None:
        discovered: list[str] = []
        for info in pkgutil.walk_packages(
            easyprent_accounting.__path__, easyprent_accounting.__name__ + "."
        ):
            discovered.append(info.name)
            imported = importlib.import_module(info.name)
            self.assertIsNotNone(imported, f"Failed to import {info.name}")

        # Ensure subpackages like integrations.gnucash are actively discovered
        self.assertIn(
            "easyprent_accounting.integrations.gnucash",
            discovered,
            "easyprent_accounting.integrations.gnucash was not discovered by walk_packages",
        )
        self.assertIn("easyprent_accounting.services", discovered)
        self.assertIn("easyprent_accounting.web", discovered)
        self.assertIn("easyprent_accounting.cli", discovered)


if __name__ == "__main__":
    unittest.main()

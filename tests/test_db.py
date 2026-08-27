from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

from src.easyprent_accounting.db import initialize_database


class DatabaseInitializationTests(unittest.TestCase):
    def test_initialize_database_creates_an_empty_database(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, "easyprent_accounting.db")
            original_database_path = os.environ.get("EASYPRENT_DB_PATH")
            os.environ["EASYPRENT_DB_PATH"] = database_path
            try:
                initialize_database()
                with sqlite3.connect(database_path) as connection:
                    organization_count = connection.execute(
                        "SELECT COUNT(*) FROM organizations"
                    ).fetchone()[0]
            finally:
                if original_database_path is None:
                    os.environ.pop("EASYPRENT_DB_PATH", None)
                else:
                    os.environ["EASYPRENT_DB_PATH"] = original_database_path

        self.assertEqual(organization_count, 0)

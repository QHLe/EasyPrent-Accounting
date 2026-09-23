from __future__ import annotations

import json
import os
import urllib.request
import unittest
from unittest import mock

from tests.support import (
    in_memory_database,
    running_server,
    temporary_database,
)


class TestSupportTests(unittest.TestCase):
    def test_seeded_in_memory_database_has_demo_data(self) -> None:
        connection = in_memory_database()
        self.addCleanup(connection.close)

        property_count = connection.execute("SELECT COUNT(*) FROM properties").fetchone()[0]

        self.assertGreater(property_count, 0)

    def test_temporary_database_is_seeded_without_mutating_environment(self) -> None:
        original_database_path = os.environ.get("EASYPRENT_DB_PATH")

        with temporary_database(seeded=True) as database:
            self.assertEqual(os.environ.get("EASYPRENT_DB_PATH"), original_database_path)
            self.assertTrue(database.path.exists())
            connection = database.connect()
            try:
                property_count = connection.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            finally:
                connection.close()

        self.assertGreater(property_count, 0)
        self.assertFalse(database.path.exists())
        self.assertEqual(os.environ.get("EASYPRENT_DB_PATH"), original_database_path)

    def test_running_asgi_server_serves_health_and_creates_v1_database(self) -> None:
        with temporary_database(initialized=False) as database:
            with mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}):
                with running_server("127.0.0.1", 0) as server:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{server.server_port}/api/v1/health"
                    ) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(json.load(response)["status"], "ok")
            with database.connect() as connection:
                self.assertEqual(
                    connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0],
                    1,
                )

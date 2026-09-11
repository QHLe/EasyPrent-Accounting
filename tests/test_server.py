from __future__ import annotations

import os
import unittest
from unittest import mock
from wsgiref.simple_server import WSGIServer

from easyprent_accounting.config import get_global_config, set_global_config
from easyprent_accounting.server import create_server, run_server, main
from tests.support import temporary_database, preserved_global_config


class ServerLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(preserved_global_config())

    def test_create_server_initializes_config_and_database(self) -> None:
        database = self.enterContext(temporary_database(initialized=False))
        self.enterContext(mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}))
        server = create_server("127.0.0.1", 0)
        self.addCleanup(server.server_close)

        self.assertIsInstance(server, WSGIServer)
        cfg = get_global_config()
        self.assertEqual(cfg.db_path, database.path)

        connection = database.connect()
        self.addCleanup(connection.close)
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        ]
        self.assertIn("organizations", tables)

    def test_run_server_delegates_to_create_server_and_serves(self) -> None:
        database = self.enterContext(temporary_database())
        self.enterContext(mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}))

        served = False

        def fake_serve_forever(httpd_self: WSGIServer) -> None:
            nonlocal served
            served = True

        with mock.patch.object(WSGIServer, "serve_forever", fake_serve_forever):
            run_server("127.0.0.1", 0)

        self.assertTrue(served)
        cfg = get_global_config()
        self.assertEqual(cfg.db_path, database.path)

    def test_main_calls_run_server(self) -> None:
        with mock.patch("easyprent_accounting.server.run_server") as mock_run:
            main()
            mock_run.assert_called_once_with()


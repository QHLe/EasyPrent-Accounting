from __future__ import annotations

import os
import threading
import unittest
from unittest import mock
from wsgiref.simple_server import WSGIServer

from easyprent_accounting.config import get_global_config
from easyprent_accounting.server import create_server, run_server, main
from tests.support import temporary_database


class ServerLifecycleTests(unittest.TestCase):
    def test_create_server_initializes_config_and_database(self) -> None:
        with temporary_database(initialized=False) as database:
            with mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}):
                server = create_server("127.0.0.1", 0)
                try:
                    self.assertIsInstance(server, WSGIServer)
                    cfg = get_global_config()
                    self.assertEqual(cfg.db_path, database.path)
                    # Verify database was initialized
                    connection = database.connect()
                    try:
                        tables = [
                            row[0]
                            for row in connection.execute(
                                "SELECT name FROM sqlite_master WHERE type = 'table'"
                            ).fetchall()
                        ]
                        self.assertIn("organizations", tables)
                    finally:
                        connection.close()
                finally:
                    server.server_close()

    def test_run_server_triggers_ready_callback_and_serves(self) -> None:
        with temporary_database() as database:
            ready_event = threading.Event()
            captured_server: list[WSGIServer] = []

            def on_ready(httpd: WSGIServer) -> None:
                captured_server.append(httpd)
                ready_event.set()

            def run():
                with mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}):
                    run_server("127.0.0.1", 0, ready_callback=on_ready)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()

            self.assertTrue(ready_event.wait(timeout=5))
            self.assertEqual(len(captured_server), 1)
            self.assertIsInstance(captured_server[0], WSGIServer)

            captured_server[0].shutdown()
            captured_server[0].server_close()
            thread.join(timeout=5)

    def test_main_calls_run_server(self) -> None:
        with mock.patch("easyprent_accounting.server.run_server") as mock_run:
            main()
            mock_run.assert_called_once_with()

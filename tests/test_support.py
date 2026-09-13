from __future__ import annotations

import os
import unittest
from unittest import mock

from tests.support import (
    call_wsgi_application,
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

    def test_wsgi_request_builder_passes_request_details_and_collects_the_response(self) -> None:
        def application(environ, start_response):
            start_response("201 Created", [("Content-Type", "text/plain")])
            return [
                (
                    f"{environ['REQUEST_METHOD']} {environ['PATH_INFO']}?"
                    f"{environ['QUERY_STRING']} {environ['CONTENT_TYPE']} "
                    f"{environ['wsgi.input'].read().decode('utf-8')}"
                ).encode("utf-8")
            ]

        response = call_wsgi_application(
            application,
            method="POST",
            path="/expenses",
            query_string="year=2025",
            content_type="text/plain",
            body=b"Winterdienst",
        )

        self.assertEqual(response.status, "201 Created")
        self.assertEqual(response.headers["Content-Type"], "text/plain")
        self.assertEqual(
            response.body,
            b"POST /expenses?year=2025 text/plain Winterdienst",
        )

    def test_running_server_starts_and_cleans_up_in_order(self) -> None:
        manager = mock.Mock()
        fake_server = mock.Mock()
        fake_thread = mock.Mock()
        manager.attach_mock(fake_server, "server")
        manager.attach_mock(fake_thread, "thread")

        with mock.patch("tests.support.create_server", return_value=fake_server), \
             mock.patch("tests.support.threading.Thread", return_value=fake_thread):
            with running_server("127.0.0.1", 0) as server:
                self.assertIs(server, fake_server)
                self.assertEqual(manager.mock_calls, [mock.call.thread.start()])

            self.assertEqual(
                manager.mock_calls,
                [
                    mock.call.thread.start(),
                    mock.call.server.shutdown(),
                    mock.call.thread.join(5),
                    mock.call.server.server_close(),
                ],
            )

    def test_running_server_closes_socket_when_thread_start_fails(self) -> None:
        manager = mock.Mock()
        fake_server = mock.Mock()
        fake_thread = mock.Mock()
        fake_thread.start.side_effect = RuntimeError("thread start failure")
        manager.attach_mock(fake_server, "server")
        manager.attach_mock(fake_thread, "thread")

        with mock.patch("tests.support.create_server", return_value=fake_server), \
             mock.patch("tests.support.threading.Thread", return_value=fake_thread):
            with self.assertRaises(RuntimeError):
                with running_server("127.0.0.1", 0):
                    pass

        self.assertEqual(
            manager.mock_calls,
            [
                mock.call.thread.start(),
                mock.call.server.server_close(),
            ],
        )

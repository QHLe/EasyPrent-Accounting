from __future__ import annotations

import os
import unittest

from tests.support import call_wsgi_application, in_memory_database, temporary_database


class TestSupportTests(unittest.TestCase):
    def test_seeded_in_memory_database_has_demo_data(self) -> None:
        connection = in_memory_database()
        self.addCleanup(connection.close)

        property_count = connection.execute("SELECT COUNT(*) FROM properties").fetchone()[0]

        self.assertGreater(property_count, 0)

    def test_temporary_database_is_seeded_and_restores_the_database_path(self) -> None:
        original_database_path = os.environ.get("EASYPRENT_DB_PATH")

        with temporary_database(seeded=True) as database:
            self.assertEqual(os.environ["EASYPRENT_DB_PATH"], str(database.path))
            connection = database.connect()
            try:
                property_count = connection.execute("SELECT COUNT(*) FROM properties").fetchone()[0]
            finally:
                connection.close()

        self.assertGreater(property_count, 0)
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

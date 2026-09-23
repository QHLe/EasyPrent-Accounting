"""Production ASGI startup and schema safety."""

from __future__ import annotations

from contextlib import redirect_stderr
from io import StringIO
import os
import sqlite3
import unittest
from unittest import mock

from easyprent_accounting import server
from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig
from fastapi.testclient import TestClient
from easyprent_accounting.runtime_schema import prepare_database
from easyprent_accounting.migration import migrate_database
from tests.legacy_fixture import create_legacy_fixture
from tests.support import temporary_database


class ServerLifecycleTests(unittest.TestCase):
    def test_new_database_is_initialized_through_versioned_runner(self) -> None:
        database = self.enterContext(temporary_database(initialized=False))
        with mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}):
            with mock.patch.object(server.uvicorn, "run") as uvicorn_run:
                self.assertEqual(server.run_server("127.0.0.1", 8765), 0)

        uvicorn_run.assert_called_once()
        self.assertEqual(uvicorn_run.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(uvicorn_run.call_args.kwargs["port"], 8765)
        with database.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0],
                1,
            )

    def test_legacy_database_aborts_without_mutation_or_binding_a_port(self) -> None:
        database = self.enterContext(temporary_database())
        before = database.path.read_bytes()
        errors = StringIO()
        with mock.patch.dict(os.environ, {"EASYPRENT_DB_PATH": str(database.path)}):
            with mock.patch.object(server.uvicorn, "run") as uvicorn_run:
                with redirect_stderr(errors):
                    self.assertEqual(server.run_server("127.0.0.1", 8765), 1)

        uvicorn_run.assert_not_called()
        self.assertEqual(database.path.read_bytes(), before)
        self.assertIn("migrate --database", errors.getvalue())
        self.assertIn("--cutover", errors.getvalue())

    def test_migrated_database_passes_preflight_without_mutation(self) -> None:
        database = self.enterContext(temporary_database(initialized=False))
        create_legacy_fixture(database.path)
        migrate_database(database.path, cutover=True)
        before = database.path.read_bytes()

        prepare_database(database.path)

        self.assertEqual(database.path.read_bytes(), before)

    def test_unknown_unversioned_schema_is_rejected_without_mutation(self) -> None:
        database = self.enterContext(temporary_database(initialized=False))
        connection = sqlite3.connect(database.path)
        connection.execute("CREATE TABLE unknown_data (value TEXT)")
        connection.commit()
        connection.close()
        before = database.path.read_bytes()

        with self.assertRaisesRegex(RuntimeError, "migrate --database"):
            prepare_database(database.path)

        self.assertEqual(database.path.read_bytes(), before)

    def test_asgi_lifespan_rejects_legacy_before_accepting_requests(self) -> None:
        database = self.enterContext(temporary_database())
        before = database.path.read_bytes()
        app = create_asgi_app(
            AppConfig(db_path=database.path, project_root=database.path.parent),
            validate_schema_on_startup=True,
        )
        with self.assertRaisesRegex(RuntimeError, "migrate --database"):
            with TestClient(app):
                self.fail("Legacy database unexpectedly passed ASGI startup")
        self.assertEqual(database.path.read_bytes(), before)

    def test_spa_fallback_serves_built_frontend_without_old_static_routes(self) -> None:
        database = self.enterContext(temporary_database(initialized=False))
        app = create_asgi_app(
            AppConfig(db_path=database.path, project_root=database.path.parent)
        )
        client = TestClient(app, raise_server_exceptions=False)
        page = client.get("/expenses")
        self.assertEqual(page.status_code, 200)
        self.assertIn('type="module"', page.text)
        self.assertEqual(client.get("/static/app.js").status_code, 404)
        self.assertEqual(client.post("/expenses").status_code, 404)
        self.assertEqual(client.get("/api/v1/obsolete").status_code, 404)

    def test_main_parses_network_arguments(self) -> None:
        with mock.patch.object(server, "run_server", return_value=0) as run:
            self.assertEqual(server.main(["--host", "127.0.0.1", "--port", "8800"]), 0)
        run.assert_called_once_with("127.0.0.1", 8800)

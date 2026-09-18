"""FastAPI application factory and domain-error-to-HTTP mapping."""

from __future__ import annotations

import sqlite3
import unittest
from unittest.mock import patch

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress
from easyprent_accounting.domain import DomainError
from easyprent_accounting.http_db import ReadConnection, WriteConnection
from tests.support import temporary_database


def _test_config(db_path: str) -> AppConfig:
    """Minimal AppConfig for testing."""
    from pathlib import Path
    return AppConfig(
        db_path=Path(db_path),
        project_root=Path(db_path).parent,
        sender=SenderAddress(),
    )


class HealthEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        from starlette.testclient import TestClient

        self.database = self.enterContext(temporary_database())
        config = _test_config(str(self.database.path))
        self.app = create_asgi_app(config)
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_health_returns_ok_with_status_and_checked_at(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["reachable"])
        self.assertIn("checked_at", body)

    def test_health_response_content_type_is_json(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertIn("application/json", response.headers["content-type"])


class AppFactoryTests(unittest.TestCase):
    def test_app_factory_stores_config_on_state(self) -> None:
        from pathlib import Path
        config = AppConfig(
            db_path=Path("/tmp/test.db"),
            project_root=Path("/tmp"),
            sender=SenderAddress(),
        )

        app = create_asgi_app(config)

        self.assertIs(app.state.config, config)

    def test_unknown_route_returns_404(self) -> None:
        from starlette.testclient import TestClient

        database = self.enterContext(temporary_database())
        config = _test_config(str(database.path))
        app = create_asgi_app(config)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/v1/nonexistent")

        self.assertEqual(response.status_code, 404)


class DomainErrorMappingTests(unittest.TestCase):
    """Point 42: DomainError → uniform HTTP 422 error format."""

    def setUp(self) -> None:
        from starlette.testclient import TestClient

        self.database = self.enterContext(temporary_database())
        config = _test_config(str(self.database.path))
        self.app = create_asgi_app(config)

        # Add a test-only route that raises DomainError
        @self.app.get("/api/v1/_test/domain-error")
        def raise_domain_error() -> None:
            raise DomainError("invalid_value", "The value is not valid.")

        @self.app.get("/api/v1/_test/domain-error-money")
        def raise_money_error() -> None:
            raise DomainError("invalid_money", "Money must be a finite Decimal.")

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_domain_error_returns_422_with_code_and_reason(self) -> None:
        response = self.client.get("/api/v1/_test/domain-error")

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["code"], "invalid_value")
        self.assertEqual(body["error"]["reason"], "The value is not valid.")

    def test_domain_error_response_is_json(self) -> None:
        response = self.client.get("/api/v1/_test/domain-error")

        self.assertIn("application/json", response.headers["content-type"])

    def test_domain_error_format_is_stable_across_different_codes(self) -> None:
        response = self.client.get("/api/v1/_test/domain-error-money")

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["code"], "invalid_money")
        self.assertEqual(body["error"]["reason"], "Money must be a finite Decimal.")

    def test_domain_error_body_has_no_extra_top_level_keys(self) -> None:
        response = self.client.get("/api/v1/_test/domain-error")

        body = response.json()
        self.assertEqual(list(body.keys()), ["error"])
        self.assertEqual(sorted(body["error"].keys()), ["code", "reason"])


class DatabaseDependencyTests(unittest.TestCase):
    """Write use cases commit or roll back at the HTTP application boundary."""

    def setUp(self) -> None:
        from starlette.testclient import TestClient

        self.database = self.enterContext(temporary_database())
        self.app = create_asgi_app(_test_config(str(self.database.path)))

        @self.app.post("/api/v1/_test/write")
        def write_two_rows(
            read: ReadConnection, connection: WriteConnection
        ) -> dict[str, int]:
            assert read is connection
            assert connection.in_transaction
            connection.execute(
                "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
                ("First", "owner"),
            )
            connection.execute(
                "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
                ("Second", "owner"),
            )
            return {"written": 2}

        @self.app.post("/api/v1/_test/write-error")
        def write_then_fail(connection: WriteConnection) -> None:
            connection.execute(
                "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
                ("Discarded", "owner"),
            )
            raise DomainError("invalid_value", "Write rejected.")

        @self.app.post("/api/v1/_test/invalid-response", response_model=dict[str, int])
        def write_then_return_invalid_response(connection: WriteConnection) -> dict:
            connection.execute(
                "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
                ("Also discarded", "owner"),
            )
            return {"written": "invalid"}

        self.client = TestClient(self.app, raise_server_exceptions=False)

    def _organization_names(self) -> list[str]:
        with self.database.connect() as connection:
            return [
                row[0]
                for row in connection.execute("SELECT name FROM organizations ORDER BY id")
            ]

    def test_success_commits_one_transaction_and_closes_connection(self) -> None:
        from easyprent_accounting.db import get_connection

        statements: list[str] = []
        opened: list[sqlite3.Connection] = []

        def record_connection(*args, **kwargs) -> sqlite3.Connection:
            connection = get_connection(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            opened.append(connection)
            return connection

        with patch("easyprent_accounting.http_db.get_connection", record_connection):
            response = self.client.post("/api/v1/_test/write")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"written": 2})
        self.assertEqual(self._organization_names(), ["First", "Second"])
        transaction_statements = [
            statement for statement in statements if statement in {"BEGIN", "COMMIT", "ROLLBACK"}
        ]
        self.assertEqual(transaction_statements, ["BEGIN", "COMMIT"])
        self.assertEqual(len(opened), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute("SELECT 1")

    def test_domain_error_rolls_back_entire_use_case(self) -> None:
        response = self.client.post("/api/v1/_test/write-error")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json(), {"error": {"code": "invalid_value", "reason": "Write rejected."}}
        )
        self.assertEqual(self._organization_names(), [])

    def test_response_validation_error_rolls_back_write(self) -> None:
        response = self.client.post("/api/v1/_test/invalid-response")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self._organization_names(), [])


if __name__ == "__main__":
    unittest.main()

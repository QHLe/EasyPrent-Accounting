"""The delivered API must work on the database produced by the explicit migrator."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig, SenderAddress
from easyprent_accounting.migration import migrate_database
from easyprent_accounting.settlements import Settlements
from tests.legacy_fixture import create_legacy_fixture
from fastapi.testclient import TestClient


class MigratedRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database = Path(self.directory) / "legacy.db"
        create_legacy_fixture(self.database)
        with sqlite3.connect(self.database) as legacy:
            legacy.row_factory = sqlite3.Row
            self.legacy_settlement = Settlements(legacy).for_period(
                None, "2025-01-01", "2025-12-31", unit_id=30
            )
        migrate_database(self.database, cutover=True)
        config = AppConfig(
            db_path=self.database,
            project_root=Path(self.directory),
            sender=SenderAddress(),
        )
        self.client = TestClient(create_asgi_app(config), raise_server_exceptions=False)

    def test_primary_read_models_load_after_migration(self) -> None:
        paths = (
            "/api/v1/health",
            "/api/v1/assets",
            "/api/v1/expenses",
            "/api/v1/expenses/development?year=2025",
            "/api/v1/metering",
            "/api/v1/tenancy",
            "/api/v1/depreciation/assets",
            "/api/v1/dashboard/summary",
            "/api/v1/settings/application",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
        assets = self.client.get("/api/v1/assets").json()
        self.assertTrue(assets["organizations"])
        self.assertTrue(assets["properties"])

    def test_property_and_expense_can_be_created_on_migrated_database(self) -> None:
        organization_id = self.client.get("/api/v1/assets").json()["organizations"][0]["id"]
        property_response = self.client.post(
            "/api/v1/properties",
            json={
                "organization_id": organization_id,
                "name": "Neue Anlage",
                "street": "Prüfweg 8",
                "city": "Teststadt",
                "postal_code": "10000",
            },
        )
        self.assertEqual(property_response.status_code, 201, property_response.text)
        property_id = property_response.json()["id"]
        expense_response = self.client.post(
            "/api/v1/expenses",
            json={
                "object_type": "property",
                "object_id": property_id,
                "expense_category": "Prüfkosten",
                "beneficiary_name": "Testversorger",
                "label": "Prüfposten",
                "amount": "25.00",
                "allocation_method": "unit_count",
                "charge_type": "one_time",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )
        self.assertEqual(expense_response.status_code, 201, expense_response.text)
        listed = self.client.get("/api/v1/expenses").json()["expenses"]
        self.assertIn(expense_response.json()["id"], {expense["id"] for expense in listed})
        property_row = next(
            row for row in self.client.get("/api/v1/assets").json()["properties"]
            if row["id"] == property_id
        )
        self.assertEqual(property_row["expense_count"], 1)

    def test_settlement_totals_survive_migration(self) -> None:
        response = self.client.get(
            "/api/v1/settlements",
            params={
                "unit_id": 30,
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        migrated = response.json()
        self.assertEqual(migrated["totals"], self.legacy_settlement["totals"])
        self.assertEqual(
            [row["allocated_costs"] for row in migrated["results"]],
            [row["allocated_costs"] for row in self.legacy_settlement["results"]],
        )


if __name__ == "__main__":
    unittest.main()

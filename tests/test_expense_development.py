"""Backend-owned cost trend for the migrated schema."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from easyprent_accounting.asgi import create_asgi_app
from easyprent_accounting.config import AppConfig
from easyprent_accounting.db import get_connection
from easyprent_accounting.schema_runner import Migration, run_migrations
from easyprent_accounting.schema_v1 import apply_schema_v1


class ExpenseDevelopmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(self.enterContext(TemporaryDirectory()))
        self.database = self.directory / "costs.db"
        connection = get_connection(self.database)
        run_migrations(connection, [Migration(1, "initial schema v1", apply_schema_v1)])
        connection.execute(
            "INSERT INTO organizations(name, organization_type) VALUES ('Test', 'private')"
        )
        connection.execute(
            "INSERT INTO properties(organization_id, name, street, city, postal_code) "
            "VALUES (1, 'House', 'Road', 'Town', '12345')"
        )
        connection.execute(
            "INSERT INTO meters(object_type, object_id, label, unit) "
            "VALUES ('property', 1, 'Heat', 'kWh')"
        )
        self._expense(connection, "Rent", "29.00", "monthly", "2024-02-15", "9999-12-31")
        self._expense(connection, "Tax", "59.00", "one_time", "2024-02-01", "2024-03-30")
        self._expense(
            connection, "Heat", "3.00", "consumption", "2024-02-01", "2024-02-29",
            meter_id=1,
        )
        self._expense(
            connection, "Archived", "1000.00", "monthly", "2024-01-01", "9999-12-31",
            is_archived=1,
        )
        connection.commit()
        connection.close()
        self.client = TestClient(
            create_asgi_app(AppConfig(db_path=self.database, project_root=self.directory)),
            raise_server_exceptions=False,
        )

    def _expense(
        self, connection, category: str, amount: str, charge_type: str,
        start: str, end: str, *, meter_id: int | None = None, is_archived: int = 0,
    ) -> None:
        connection.execute(
            """
            INSERT INTO expense_items (
                object_type, object_id, expense_category, beneficiary_name, label,
                amount, allocation_method, charge_type, meter_id, conversion_factor,
                period_start, period_end, is_archived
            ) VALUES ('property', 1, ?, 'Utility', ?, ?, 'occupants', ?, ?, 1, ?, ?, ?)
            """,
            (category, category, amount, charge_type, meter_id, start, end, is_archived),
        )

    def test_leap_year_pricing_and_unknown_meter_are_projected_without_partial_totals(self) -> None:
        response = self.client.get("/api/v1/expenses/development", params={"year": 2024})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result["months"]), 12)
        self.assertEqual([row["expense_category"] for row in result["categories"]], ["Heat", "Rent", "Tax"])
        self.assertEqual(result["months"][0]["total_amount"], "0.00")
        february = result["months"][1]
        self.assertIsNone(february["total_amount"])
        self.assertTrue(february["has_uncalculated_expense"])
        amounts = {row["expense_category"]: row["amount"] for row in february["categories"]}
        self.assertEqual(amounts, {"Heat": None, "Rent": "15.00", "Tax": "29.00"})
        march = result["months"][2]
        self.assertEqual(march["total_amount"], "59.00")
        self.assertEqual(result["total_amount"], None)
        self.assertNotIn("Archived", [row["expense_category"] for row in result["categories"]])

    def test_meter_readings_resolve_unknown_amount_using_backend_interpolation(self) -> None:
        connection = get_connection(self.database)
        connection.executemany(
            "INSERT INTO meter_readings(meter_id, reading_date, reading_value) VALUES (1, ?, ?)",
            [("2024-02-01", "0"), ("2024-03-01", "10")],
        )
        connection.commit()
        connection.close()

        response = self.client.get("/api/v1/expenses/development?year=2024")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        february = result["months"][1]
        self.assertFalse(february["has_uncalculated_expense"])
        self.assertEqual(february["total_amount"], "74.00")
        self.assertEqual(result["total_amount"], "394.00")

    def test_annual_total_uses_full_year_price_before_monthly_rounding(self) -> None:
        connection = get_connection(self.database)
        connection.execute("UPDATE expense_items SET is_archived = 1")
        self._expense(
            connection, "Rounding", "0.01", "one_time", "2025-01-01", "2025-03-31"
        )
        connection.commit()
        connection.close()

        response = self.client.get("/api/v1/expenses/development?year=2025")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["total_amount"], "0.01")
        self.assertEqual(result["categories"], [{
            "expense_category": "Rounding",
            "amount": "0.01",
            "has_uncalculated_expense": False,
        }])
        self.assertEqual(
            [month["total_amount"] for month in result["months"][:3]],
            ["0.00", "0.00", "0.00"],
        )

    def test_year_validation_uses_common_error_envelope(self) -> None:
        response = self.client.get("/api/v1/expenses/development?year=9999")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

"""Expense HTTP contracts exercised through the ASGI application."""

from __future__ import annotations

import unittest

from tests.support import asgi_test_client, temporary_database


class ExpenseHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def _expense(self, **overrides: object) -> dict:
        return {
            "object_type": "property",
            "object_id": 1,
            "expense_category": "Water",
            "beneficiary_name": "Utility",
            "amount": "12.50",
            "allocation_method": "occupants",
            "charge_type": "one_time",
            "booking_date": "2025-01-01",
            **overrides,
        }

    def test_all_charge_variants_are_created_and_listed(self) -> None:
        original_count = len(self.client.get("/api/v1/expenses").json()["expenses"])
        cases = (
            ("one_time", {"booking_date": "2025-01-01"}, "12.50"),
            ("total", {"booking_date": "2025-01-01"}, "12.50"),
            ("monthly", {"period_start": "2025-01-01", "period_end": "2025-01-31"}, "12.50"),
            ("quarterly", {"period_start": "2025-01-01", "period_end": "2025-03-31"}, "12.50"),
            ("yearly", {"period_start": "2025-01-01", "period_end": "2025-12-31"}, "12.50"),
            ("consumption", {"period_start": "2025-01-01", "period_end": "2025-01-31", "consumption_unit": "m3", "consumption_value": "3"}, "37.50"),
        )
        for charge_type, fields, expected_total in cases:
            with self.subTest(charge_type=charge_type):
                payload = self._expense(charge_type=charge_type, **fields)
                response = self.client.post("/api/v1/expenses", json=payload)
                self.assertEqual(response.status_code, 201, response.text)
                self.assertEqual(response.json()["total_amount"], expected_total)
                self.assertEqual(response.headers["content-type"], "application/json")

        listed = self.client.get("/api/v1/expenses")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(len(listed.json()["expenses"]), original_count + len(cases))

    def test_metered_consumption_update_and_lifecycle(self) -> None:
        meter = self.client.post("/api/v1/meters", json={
            "object_type": "property", "object_id": 1,
            "label": "Water", "meter_type": "water", "unit": "m3",
        })
        self.assertEqual(meter.status_code, 201, meter.text)
        meter_id = meter.json()["id"]
        for reading_date, value in (("2025-01-01", "2"), ("2025-02-01", "5")):
            reading = self.client.post("/api/v1/meter-readings", json={
                "meter_id": meter_id, "reading_date": reading_date, "reading_value": value,
            })
            self.assertEqual(reading.status_code, 201, reading.text)
        payload = self._expense(
            charge_type="consumption", booking_date=None,
            period_start="2025-01-01", period_end="2025-01-31", meter_id=meter_id,
            conversion_factor="2",
        )
        created = self.client.post("/api/v1/expenses", json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["effective_consumption_value"], "6")
        expense_id = created.json()["id"]

        updated = self.client.put(f"/api/v1/expenses/{expense_id}", json={
            **payload, "amount": "2.00",
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["total_amount"], "12.00")
        archived = self.client.post(f"/api/v1/expenses/{expense_id}/archive")
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertEqual(archived.json()["is_archived"], True)
        blocked = self.client.put(f"/api/v1/expenses/{expense_id}", json=payload)
        self.assertEqual(blocked.status_code, 422)
        self.assertEqual(blocked.json()["error"]["code"], "invalid_value")
        self.assertEqual(self.client.post(f"/api/v1/expenses/{expense_id}/restore").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/expenses/{expense_id}/archive").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/expenses/{expense_id}").json()["deleted"], True)

    def test_open_ended_recurring_expense_has_no_period_total(self) -> None:
        created = self.client.post("/api/v1/expenses", json=self._expense(
            charge_type="monthly", booking_date=None, period_start="2025-01-01",
        ))
        self.assertEqual(created.status_code, 201, created.text)
        self.assertTrue(created.json()["is_open_ended"])
        self.assertIsNone(created.json()["period_end"])
        self.assertIsNone(created.json()["total_amount"])
        listed = self.client.get("/api/v1/expenses").json()["expenses"]
        selected = next(row for row in listed if row["id"] == created.json()["id"])
        self.assertTrue(selected["is_open_ended"])

    def test_invalid_payload_is_rejected_without_an_insert(self) -> None:
        original_count = len(self.client.get("/api/v1/expenses").json()["expenses"])
        response = self.client.post("/api/v1/expenses", json=self._expense(amount=12.5))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")
        self.assertIn("amount", response.json()["error"]["reason"])
        self.assertEqual(len(self.client.get("/api/v1/expenses").json()["expenses"]), original_count)


if __name__ == "__main__":
    unittest.main()

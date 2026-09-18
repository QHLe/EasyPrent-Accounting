"""Metering HTTP behavior through the application and real module."""

from __future__ import annotations

import unittest

from tests.support import asgi_test_client, temporary_database


class MeteringHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_readings_are_monotone_and_consumption_is_decimal_text(self) -> None:
        meter = self.client.post("/api/v1/meters", json={
            "object_type": "property", "object_id": 1,
            "label": "Cold water", "meter_type": "water", "unit": "m3",
        })
        self.assertEqual(meter.status_code, 201, meter.text)
        meter_id = meter.json()["id"]
        first = self.client.post("/api/v1/meter-readings", json={
            "meter_id": meter_id, "reading_date": "2025-01-01", "reading_value": "10.25",
        })
        self.assertEqual(first.status_code, 201, first.text)
        last = self.client.post("/api/v1/meter-readings", json={
            "meter_id": meter_id, "reading_date": "2025-02-01", "reading_value": "13.75",
        })
        self.assertEqual(last.status_code, 201, last.text)
        invalid = self.client.post("/api/v1/meter-readings", json={
            "meter_id": meter_id, "reading_date": "2025-01-15", "reading_value": "14",
        })
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["error"]["code"], "invalid_value")
        self.assertIn("later reading", invalid.json()["error"]["reason"])

        listed = self.client.get("/api/v1/metering")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(
            [row["reading_value"] for row in listed.json()["meter_readings"] if row["meter_id"] == meter_id],
            ["10.25", "13.75"],
        )
        consumption = self.client.get(
            f"/api/v1/meters/{meter_id}/consumption",
            params={"start": "2025-01-01", "end": "2025-01-31"},
        )
        self.assertEqual(consumption.status_code, 200, consumption.text)
        self.assertEqual(consumption.json()["quantity"], "3.50")
        missing = self.client.get(
            "/api/v1/meters/999/consumption",
            params={"start": "2025-01-01", "end": "2025-01-31"},
        )
        self.assertEqual(missing.status_code, 422)
        self.assertIn("meter not found", missing.json()["error"]["reason"])

    def test_meter_edit_and_lifecycle_are_persisted(self) -> None:
        payload = {"object_type": "property", "object_id": 1, "label": "Water", "unit": "m3"}
        created = self.client.post("/api/v1/meters", json=payload)
        self.assertEqual(created.status_code, 201, created.text)
        meter_id = created.json()["id"]
        updated = self.client.put(f"/api/v1/meters/{meter_id}", json={**payload, "label": "Water main"})
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()["label"], "Water main")
        archived = self.client.post(f"/api/v1/meters/{meter_id}/archive")
        self.assertEqual(archived.status_code, 200, archived.text)
        self.assertTrue(archived.json()["is_archived"])
        blocked = self.client.put(f"/api/v1/meters/{meter_id}", json=payload)
        self.assertEqual(blocked.status_code, 422)
        self.assertEqual(self.client.post(f"/api/v1/meters/{meter_id}/restore").status_code, 200)
        self.assertEqual(self.client.post(f"/api/v1/meters/{meter_id}/archive").status_code, 200)
        deleted = self.client.delete(f"/api/v1/meters/{meter_id}")
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertTrue(deleted.json()["deleted"])


if __name__ == "__main__":
    unittest.main()

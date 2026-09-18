"""Tenant and lease HTTP behavior through the real Tenancy module."""

from __future__ import annotations

import unittest

from easyprent_accounting.asset_registry import AssetRegistry
from tests.support import asgi_test_client, temporary_database


class TenancyHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)
        connection = self.database.connect(rows=True)
        try:
            self.room_id = AssetRegistry(connection).create_room({
                "unit_id": 1, "label": "North room", "area_sqm": "19.5",
                "area_share_percent": "26.17",
            })["id"]
            connection.commit()
        finally:
            connection.close()

    def _lease(self, tenant_id: int, **overrides: object) -> dict:
        return {
            "tenant_id": tenant_id, "room_id": self.room_id,
            "rent_cold": "450.00", "additional_charges_advance": "85.25",
            "occupant_count": 1, "start_date": "2025-02-01", "end_date": "2025-06-30",
            "status": "active", **overrides,
        }

    def test_room_assignment_and_contract_period_round_trip(self) -> None:
        tenant = self.client.post("/api/v1/tenants", json={
            "full_name": "Mira Example", "email": "mira@example.test",
        })
        self.assertEqual(tenant.status_code, 201, tenant.text)
        tenant_id = tenant.json()["id"]
        lease = self.client.post("/api/v1/leases", json=self._lease(tenant_id))
        self.assertEqual(lease.status_code, 201, lease.text)
        self.assertEqual(lease.json()["unit_id"], 1)
        self.assertEqual(lease.json()["room_id"], self.room_id)
        self.assertEqual(lease.json()["rent_cold"], "450.00")
        lease_id = lease.json()["id"]

        listed = self.client.get("/api/v1/tenancy")
        self.assertEqual(listed.status_code, 200, listed.text)
        selected = next(row for row in listed.json()["leases"] if row["id"] == lease_id)
        self.assertEqual(selected["rental_object_type"], "room")
        self.assertEqual(selected["start_date"], "2025-02-01")
        self.assertEqual(selected["end_date"], "2025-06-30")

        updated = self.client.put(f"/api/v1/leases/{lease_id}", json=self._lease(
            tenant_id, end_date=None, additional_charges_advance="90.00",
        ))
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertIsNone(updated.json()["end_date"])
        self.assertEqual(updated.json()["additional_charges_advance"], "90.00")
        self.assertEqual(self.client.delete(f"/api/v1/leases/{lease_id}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/tenants/{tenant_id}").status_code, 200)

    def test_invalid_period_or_room_assignment_is_rejected(self) -> None:
        tenant = self.client.post("/api/v1/tenants", json={"full_name": "Mira Example"})
        tenant_id = tenant.json()["id"]
        for payload in (
            self._lease(tenant_id, end_date="2025-01-31"),
            self._lease(tenant_id, unit_id=2),
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/v1/leases", json=payload)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(response.json()["error"]["code"], "invalid_value")

    def test_tenant_update_is_visible_in_list(self) -> None:
        created = self.client.post("/api/v1/tenants", json={"full_name": "Old Name"})
        self.assertEqual(created.status_code, 201, created.text)
        tenant_id = created.json()["id"]
        updated = self.client.put(f"/api/v1/tenants/{tenant_id}", json={
            "full_name": "New Name", "alternate_city": "Potsdam",
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        listed = self.client.get("/api/v1/tenancy").json()["tenants"]
        selected = next(row for row in listed if row["id"] == tenant_id)
        self.assertEqual(selected["full_name"], "New Name")
        self.assertEqual(selected["alternate_city"], "Potsdam")


if __name__ == "__main__":
    unittest.main()

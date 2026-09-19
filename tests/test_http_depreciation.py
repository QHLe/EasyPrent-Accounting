"""Depreciation HTTP use cases."""

from __future__ import annotations

import unittest

from tests.support import asgi_test_client, temporary_database


class DepreciationHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_depreciation_asset_lifecycle(self) -> None:
        payload = {
            "property_id": 1,
            "asset_name": "New Roof",
            "acquisition_cost": "25000.00",
            "building_share_percent": "100.0",
            "useful_life_years": 25,
            "placed_in_service": "2025-06-01",
        }
        create_response = self.client.post("/api/v1/depreciation/assets", json=payload)
        self.assertEqual(create_response.status_code, 201, create_response.text)
        
        asset_id = create_response.json()["id"]
        
        list_response = self.client.get("/api/v1/depreciation/assets")
        self.assertEqual(list_response.status_code, 200, list_response.text)
        
        assets = list_response.json()
        self.assertTrue(any(a["id"] == asset_id for a in assets))

    def test_depreciation_schedule(self) -> None:
        schedule_response = self.client.get("/api/v1/depreciation/schedule/2025")
        self.assertEqual(schedule_response.status_code, 200, schedule_response.text)
        data = schedule_response.json()
        self.assertEqual(data["year"], 2025)
        self.assertIn("rows", data)
        self.assertIn("total", data)


if __name__ == "__main__":
    unittest.main()


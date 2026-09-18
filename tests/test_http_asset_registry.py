"""Asset Registry HTTP use cases and lifecycle."""

from __future__ import annotations

import unittest

from tests.support import asgi_test_client, temporary_database


class AssetRegistryHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = self.enterContext(temporary_database(seeded=True))
        self.client = asgi_test_client(self.database)

    def test_asset_hierarchy_create_update_list_and_lifecycle(self) -> None:
        property_payload = {
            "organization_id": 1, "name": "New estate",
            "street": "Main 1", "city": "Berlin", "postal_code": "10115",
        }
        prop = self.client.post("/api/v1/properties", json=property_payload)
        self.assertEqual(prop.status_code, 201, prop.text)
        property_id = prop.json()["id"]
        building_payload = {
            "property_id": property_id, "name": "North building", "year_built": 2010,
            "street": "Main 1", "city": "Berlin", "postal_code": "10115",
        }
        building = self.client.post("/api/v1/buildings", json=building_payload)
        self.assertEqual(building.status_code, 201, building.text)
        building_id = building.json()["id"]
        unit_payload = {
            "building_id": building_id, "label": "N-1", "area_sqm": "75.5",
            "mea_percent": "40.25", "room_count": 1,
        }
        unit = self.client.post("/api/v1/units", json=unit_payload)
        self.assertEqual(unit.status_code, 201, unit.text)
        unit_id = unit.json()["id"]
        self.assertEqual(unit.json()["street"], "Main 1")
        room_payload = {
            "unit_id": unit_id, "label": "Office", "area_sqm": "20.5",
            "area_share_percent": "27.15",
        }
        room = self.client.post("/api/v1/rooms", json=room_payload)
        self.assertEqual(room.status_code, 201, room.text)
        room_id = room.json()["id"]
        self.assertEqual(room.json()["area_share_percent"], "27.15")

        for resource, resource_id, payload, changed_field in (
            ("properties", property_id, {**property_payload, "name": "Updated estate"}, "name"),
            ("buildings", building_id, {**building_payload, "name": "Updated building"}, "name"),
            ("units", unit_id, {**unit_payload, "label": "N-2"}, "label"),
            ("rooms", room_id, {**room_payload, "label": "Study"}, "label"),
        ):
            with self.subTest(resource=resource):
                updated = self.client.put(f"/api/v1/{resource}/{resource_id}", json=payload)
                self.assertEqual(updated.status_code, 200, updated.text)
                self.assertEqual(updated.json()[changed_field], payload[changed_field])

        listed = self.client.get("/api/v1/assets")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual(
            next(row for row in listed.json()["rooms"] if row["id"] == room_id)["unit_id"],
            unit_id,
        )
        for resource, resource_id in (
            ("rooms", room_id), ("units", unit_id),
            ("buildings", building_id), ("properties", property_id),
        ):
            with self.subTest(delete=resource):
                archive = self.client.post(f"/api/v1/{resource}/{resource_id}/archive")
                self.assertEqual(archive.status_code, 200, archive.text)
                self.assertTrue(archive.json()["is_archived"])
                deleted = self.client.delete(f"/api/v1/{resource}/{resource_id}")
                self.assertEqual(deleted.status_code, 200, deleted.text)
                self.assertTrue(deleted.json()["deleted"])

    def test_dependent_asset_cannot_be_deleted_and_restore_allows_edit(self) -> None:
        result = self.client.post("/api/v1/properties/1/archive")
        self.assertEqual(result.status_code, 200, result.text)
        blocked = self.client.delete("/api/v1/properties/1")
        self.assertEqual(blocked.status_code, 422)
        self.assertIn("dependencies", blocked.json()["error"]["reason"])
        restored = self.client.post("/api/v1/properties/1/restore")
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertFalse(restored.json()["is_archived"])

    def test_unknown_parent_ids_are_validation_errors(self) -> None:
        invalid_property = self.client.post("/api/v1/properties", json={
            "organization_id": 999, "name": "Orphaned estate",
            "street": "Main 1", "city": "Berlin", "postal_code": "10115",
        })
        self.assertEqual(invalid_property.status_code, 422, invalid_property.text)
        self.assertEqual(invalid_property.json()["error"]["code"], "invalid_value")
        invalid_building = self.client.post("/api/v1/buildings", json={
            "property_id": 999, "name": "Orphaned building",
            "street": "Main 1", "city": "Berlin", "postal_code": "10115",
        })
        self.assertEqual(invalid_building.status_code, 422, invalid_building.text)
        self.assertEqual(invalid_building.json()["error"]["code"], "invalid_value")
        assets = self.client.get("/api/v1/assets").json()
        property_row = assets["properties"][0]
        building_row = assets["buildings"][0]
        invalid_property_update = self.client.put(
            f"/api/v1/properties/{property_row['id']}",
            json={
                **{field: property_row[field] for field in (
                    "organization_id", "name", "street", "city", "postal_code"
                )},
                "organization_id": 999,
            },
        )
        self.assertEqual(invalid_property_update.status_code, 422)
        invalid_building_update = self.client.put(
            f"/api/v1/buildings/{building_row['id']}",
            json={
                **{field: building_row[field] for field in (
                    "property_id", "name", "year_built", "street", "city", "postal_code"
                )},
                "property_id": 999,
            },
        )
        self.assertEqual(invalid_building_update.status_code, 422)


if __name__ == "__main__":
    unittest.main()

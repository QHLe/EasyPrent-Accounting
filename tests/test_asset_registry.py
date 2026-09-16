from __future__ import annotations

import unittest

from easyprent_accounting.asset_registry import AssetRegistry
from tests.support import in_memory_database


class AssetRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.registry = AssetRegistry(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_unit_inherits_building_address_and_can_become_standalone(self) -> None:
        building = self.registry.create_building(
            {
                "property_id": None,
                "name": "Freistehendes Haus",
                "year_built": 2001,
                "street": "Nordweg 5",
                "city": "Berlin",
                "postal_code": "10115",
            }
        )
        unit = self.registry.create_unit(
            {
                "building_id": building["id"],
                "label": "Wohnung 1",
                "area_sqm": "58.5",
                "mea_percent": "12.5",
                "room_count": 2,
                "street": "Abweichender Weg 1",
                "city": "Potsdam",
                "postal_code": "14467",
            }
        )

        self.assertIsNone(building["property_id"])
        self.assertEqual(
            (unit["street"], unit["city"], unit["postal_code"]),
            ("Nordweg 5", "Berlin", "10115"),
        )

        standalone = self.registry.update_unit(
            unit["id"],
            {
                "building_id": None,
                "label": "Wohnung 1",
                "area_sqm": "58.5",
                "mea_percent": "12.5",
                "room_count": 2,
                "street": "Abweichender Weg 1",
                "city": "Potsdam",
                "postal_code": "14467",
            },
        )
        self.assertEqual(
            (standalone["street"], standalone["city"], standalone["postal_code"]),
            ("Abweichender Weg 1", "Potsdam", "14467"),
        )

    def test_property_lifecycle_is_idempotent_and_blocks_deletion_with_building(self) -> None:
        property_ = self.registry.create_property(
            {
                "organization_id": 1,
                "name": "Nordhof",
                "street": "Nordweg 1",
                "city": "Berlin",
                "postal_code": "10115",
            }
        )
        self.registry.create_building(
            {
                "property_id": property_["id"],
                "name": "Haus A",
                "street": "Nordweg 1",
                "city": "Berlin",
                "postal_code": "10115",
            }
        )

        archived = self.registry.archive_property(property_["id"])
        self.assertEqual(archived, self.registry.archive_property(property_["id"]))
        self.assertEqual(archived["is_archived"], 1)
        self.assertIsNotNone(archived["archived_at"])
        with self.assertRaisesRegex(ValueError, "dependencies"):
            self.registry.delete_property(property_["id"])

        restored = self.registry.restore_property(property_["id"])
        self.assertEqual(restored, self.registry.restore_property(property_["id"]))
        self.assertEqual(restored["is_archived"], 0)
        self.assertIsNone(restored["archived_at"])

    def test_room_capacity_and_archive_rules_apply_through_named_operations(self) -> None:
        unit = self.registry.create_unit(
            {
                "building_id": None,
                "label": "Kleine Wohnung",
                "area_sqm": "35",
                "mea_percent": "5",
                "room_count": 1,
                "street": "Sonnenallee 10",
                "city": "Berlin",
                "postal_code": "12045",
            }
        )
        room = self.registry.create_room({"unit_id": unit["id"], "label": "Zimmer 1"})

        with self.assertRaisesRegex(ValueError, "room_count"):
            self.registry.create_room({"unit_id": unit["id"], "label": "Zimmer 2"})
        with self.assertRaisesRegex(ValueError, "room_count"):
            self.registry.update_unit(
                unit["id"],
                {
                    "building_id": None,
                    "label": "Kleine Wohnung",
                    "area_sqm": "35",
                    "mea_percent": "5",
                    "room_count": 0,
                    "street": "Sonnenallee 10",
                    "city": "Berlin",
                    "postal_code": "12045",
                },
            )

        self.registry.archive_room(room["id"])
        with self.assertRaisesRegex(ValueError, "archived"):
            self.registry.update_room(
                room["id"], {"unit_id": unit["id"], "label": "Neuer Name"}
            )
        self.registry.delete_room(room["id"])
        replacement = self.registry.create_room(
            {"unit_id": unit["id"], "label": "Zimmer 2"}
        )
        self.assertEqual(replacement["unit_id"], unit["id"])

    def test_caller_can_roll_back_asset_creation(self) -> None:
        property_ = self.registry.create_property(
            {
                "organization_id": 1,
                "name": "Nur im Entwurf",
                "street": "Testweg 1",
                "city": "Berlin",
                "postal_code": "10115",
            }
        )

        self.connection.rollback()

        with self.assertRaisesRegex(ValueError, "property not found"):
            self.registry.archive_property(property_["id"])

    def test_list_assets_includes_standalone_unit_and_normalized_room_area(self) -> None:
        unit = self.registry.create_unit(
            {
                "building_id": None,
                "label": "Dachgeschoss",
                "area_sqm": "42",
                "mea_percent": "10",
                "room_count": 1,
                "street": "Sonnenallee 10",
                "city": "Berlin",
                "postal_code": "12045",
            }
        )
        room = self.registry.create_room(
            {
                "unit_id": unit["id"],
                "label": "Schlafzimmer",
                "area_sqm": "12.00",
                "area_share_percent": "25.00",
            }
        )

        assets = self.registry.list_assets()

        listed_unit = next(item for item in assets["units"] if item["id"] == unit["id"])
        listed_room = next(item for item in assets["rooms"] if item["id"] == room["id"])
        self.assertIsNone(listed_unit["property_id"])
        self.assertEqual(listed_unit["actual_room_count"], 1)
        self.assertEqual(listed_room["unit_label"], "Dachgeschoss")
        self.assertEqual(listed_room["area_sqm"], "12")
        self.assertEqual(listed_room["area_share_percent"], "25")


if __name__ == "__main__":
    unittest.main()

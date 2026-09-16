from __future__ import annotations

import unittest

from easyprent_accounting.asset_registry import AssetRegistry
from easyprent_accounting.services import create_depreciation_asset, list_overview
from easyprent_accounting.domain import DomainError
from decimal import Decimal
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



class PropertyRelationshipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.registry = AssetRegistry(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_create_building_allows_standalone_without_property(self) -> None:
        created = self.registry.create_building(
            {
                "property_id": None,
                "name": "Einzelgebaeude Nord",
                "year_built": 2004,
                "street": "Nordweg 5",
                "city": "Berlin",
                "postal_code": "10115",
            },
        )
        row = self.connection.execute(
            "SELECT property_id, name, street, city, postal_code FROM buildings WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertIsNone(row["property_id"])
        self.assertEqual(row["name"], "Einzelgebaeude Nord")
        self.assertEqual(row["street"], "Nordweg 5")
        self.assertEqual(row["city"], "Berlin")
        self.assertEqual(row["postal_code"], "10115")

    def test_create_unit_allows_standalone_without_building(self) -> None:
        created = self.registry.create_unit(
            {
                "building_id": None,
                "label": "Whg-Solo-1",
                "area_sqm": "58.5",
                "mea_percent": "12.5",
                "room_count": 2,
                "street": "Sonnenallee 10",
                "city": "Berlin",
                "postal_code": "12045",
            },
        )
        row = self.connection.execute(
            "SELECT building_id, label, mea_percent, street, city, postal_code FROM units WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertIsNone(row["building_id"])
        self.assertEqual(row["label"], "Whg-Solo-1")
        self.assertEqual(row["mea_percent"], 12.5)
        self.assertEqual(row["street"], "Sonnenallee 10")
        self.assertEqual(row["city"], "Berlin")
        self.assertEqual(row["postal_code"], "12045")

    def test_create_unit_requires_mea_percent(self) -> None:
        with self.assertRaises(ValueError) as error:
            self.registry.create_unit(
                {
                    "building_id": None,
                    "label": "Whg-Solo-1",
                    "area_sqm": "58.5",
                    "room_count": 2,
                    "street": "Sonnenallee 10",
                    "city": "Berlin",
                    "postal_code": "12045",
                },
            )

        self.assertIn("mea_percent", str(error.exception))

    def test_create_unit_rejects_non_finite_mea_percent(self) -> None:
        with self.assertRaises(DomainError) as caught:
            self.registry.create_unit(
                {
                    "building_id": None,
                    "label": "Whg-Solo-1",
                    "area_sqm": "58.5",
                    "mea_percent": "NaN",
                    "room_count": 2,
                    "street": "Sonnenallee 10",
                    "city": "Berlin",
                    "postal_code": "12045",
                },
            )

        self.assertEqual("invalid_percentage", caught.exception.code)

    def test_create_unit_inherits_address_from_building(self) -> None:
        created = self.registry.create_unit(
            {
                "building_id": 1,
                "label": "A-04",
                "area_sqm": "56.0",
                "mea_percent": "10",
                "room_count": 2,
                "street": "Abweichende Straße 1",
                "city": "Hamburg",
                "postal_code": "20095",
            },
        )

        row = self.connection.execute(
            "SELECT street, city, postal_code FROM units WHERE id = ?", (created["id"],)
        ).fetchone()
        self.assertEqual(dict(row), {"street": "Lindenweg 12", "city": "Berlin", "postal_code": "10439"})

    def test_update_unit_inherits_address_from_new_building(self) -> None:
        building = self.registry.create_building(
            {
                "property_id": 1,
                "name": "Haus B",
                "year_built": 2010,
                "street": "Birkenstraße 7",
                "city": "Potsdam",
                "postal_code": "14467",
            },
        )

        self.registry.update_unit(
            1,
            {
                "building_id": building["id"],
                "label": "A-01",
                "area_sqm": "74.5",
                "mea_percent": "34.1",
                "room_count": 3,
                "street": "Abweichende Straße 1",
                "city": "Hamburg",
                "postal_code": "20095",
            },
        )

        row = self.connection.execute(
            "SELECT street, city, postal_code FROM units WHERE id = 1"
        ).fetchone()
        self.assertEqual(dict(row), {"street": "Birkenstraße 7", "city": "Potsdam", "postal_code": "14467"})

    def test_update_unit_rejects_percentage_above_one_hundred(self) -> None:
        original = self.connection.execute(
            "SELECT mea_percent FROM units WHERE id = 1"
        ).fetchone()[0]

        with self.assertRaises(DomainError) as caught:
            self.registry.update_unit(
                1,
                {
                    "building_id": 1,
                    "label": "A-01",
                    "area_sqm": "74.5",
                    "mea_percent": "100.01",
                    "room_count": 3,
                    "street": "ignored",
                    "city": "ignored",
                    "postal_code": "00000",
                },
            )

        self.assertEqual("invalid_percentage", caught.exception.code)
        self.assertEqual(
            Decimal(str(original)),
            Decimal(
                str(
                    self.connection.execute(
                        "SELECT mea_percent FROM units WHERE id = 1"
                    ).fetchone()[0]
                )
            ),
        )

    def test_create_room_requires_unit(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.create_room(
                {
                    "unit_id": None,
                    "label": "Zimmer 1",
                },
            )

    def test_create_room_belongs_to_unit(self) -> None:
        created = self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Zimmer links",
            },
        )
        row = self.connection.execute(
            "SELECT unit_id, label FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(row["unit_id"], 1)
        self.assertEqual(row["label"], "Zimmer links")

    def test_create_room_stores_area_share_percent(self) -> None:
        created = self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Zimmer links",
                "area_share_percent": "37.5",
            },
        )

        row = self.connection.execute(
            "SELECT area_share_percent FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()

        self.assertEqual(created["area_share_percent"], "37.5")
        self.assertEqual(row["area_share_percent"], 37.5)

    def test_create_room_rejects_area_share_outside_percentage_range(self) -> None:
        with self.assertRaises(ValueError) as error:
            self.registry.create_room(
                {
                    "unit_id": 1,
                    "label": "Zimmer links",
                    "area_share_percent": "100.01",
                },
            )

        self.assertIn("between 0 and 100", str(error.exception))

    def test_update_room_rejects_non_finite_area_share_percent(self) -> None:
        room = self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Zimmer links",
                "area_share_percent": "37.5",
            },
        )

        with self.assertRaises(DomainError) as caught:
            self.registry.update_room(
                room["id"],
                {
                    "unit_id": 1,
                    "label": "Zimmer links",
                    "area_share_percent": "Infinity",
                },
            )

        stored = self.connection.execute(
            "SELECT area_share_percent FROM rooms WHERE id = ?", (room["id"],)
        ).fetchone()[0]
        self.assertEqual("invalid_percentage", caught.exception.code)
        self.assertEqual(Decimal("37.5"), Decimal(str(stored)))

    def test_create_depreciation_asset_rejects_invalid_domain_values(self) -> None:
        existing_count = self.connection.execute(
            "SELECT COUNT(*) FROM depreciation_assets"
        ).fetchone()[0]
        invalid_values = (
            ("Infinity", "80", "invalid_money"),
            ("500000", "101", "invalid_percentage"),
            ("500000", "NaN", "invalid_percentage"),
        )

        for acquisition_cost, building_share_percent, expected_code in invalid_values:
            with self.subTest(
                acquisition_cost=acquisition_cost,
                building_share_percent=building_share_percent,
            ):
                with self.assertRaises(DomainError) as caught:
                    create_depreciation_asset(
                        self.connection,
                        {
                            "property_id": 1,
                            "asset_name": "Gebäude",
                            "acquisition_cost": acquisition_cost,
                            "building_share_percent": building_share_percent,
                            "useful_life_years": 40,
                            "placed_in_service": "2025-01-01",
                            "method": "linear",
                        },
                    )
                self.assertEqual(expected_code, caught.exception.code)

        self.assertEqual(
            existing_count,
            self.connection.execute(
                "SELECT COUNT(*) FROM depreciation_assets"
            ).fetchone()[0],
        )

    def test_create_depreciation_asset_validates_date_and_useful_life_before_insert(self) -> None:
        payload = {
            "property_id": 1,
            "asset_name": "Gebäude",
            "acquisition_cost": "500000",
            "building_share_percent": "80",
            "useful_life_years": 40,
            "placed_in_service": "2025-01-01",
        }
        existing_count = self.connection.execute(
            "SELECT COUNT(*) FROM depreciation_assets"
        ).fetchone()[0]

        for invalid in (
            {"placed_in_service": "2025-02-30"},
            {"useful_life_years": 0},
            {"useful_life_years": -1},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                create_depreciation_asset(self.connection, {**payload, **invalid})

        self.assertEqual(
            existing_count,
            self.connection.execute("SELECT COUNT(*) FROM depreciation_assets").fetchone()[0],
        )

    def test_create_depreciation_asset_normalizes_date_and_useful_life(self) -> None:
        created = create_depreciation_asset(
            self.connection,
            {
                "property_id": 1,
                "asset_name": "Gebäude",
                "acquisition_cost": "500000",
                "building_share_percent": "80",
                "useful_life_years": "40",
                "placed_in_service": "20250102",
            },
        )

        stored = self.connection.execute(
            "SELECT useful_life_years, placed_in_service FROM depreciation_assets WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual((40, "2025-01-02"), tuple(stored))
        self.assertEqual(40, created["useful_life_years"])
        self.assertEqual("2025-01-02", created["placed_in_service"])

    def test_create_room_rejects_more_rooms_than_unit_allows(self) -> None:
        self.registry.create_room(
            {
                "unit_id": 2,
                "label": "Zimmer 1",
            },
        )
        self.registry.create_room(
            {
                "unit_id": 2,
                "label": "Zimmer 2",
            },
        )

        with self.assertRaises(ValueError) as error:
            self.registry.create_room(
                {
                    "unit_id": 2,
                    "label": "Zimmer 3",
                },
            )

        self.assertIn("room_count", str(error.exception))

    def test_list_overview_enriches_object_relationships_for_preview(self) -> None:
        self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Wohnzimmer",
            },
        )

        overview = list_overview(self.connection)
        property_row = overview["properties"][0]
        building_row = overview["buildings"][0]
        unit_row = overview["units"][0]
        room_row = overview["rooms"][0]
        expense_row = overview["expenses"][0]

        self.assertEqual(property_row["name"], "Wohnpark Lindenhof")
        self.assertEqual(property_row["building_count"], 1)
        self.assertEqual(property_row["unit_count"], 3)
        self.assertEqual(property_row["room_count"], 1)

        self.assertEqual(building_row["name"], "Haus A")
        self.assertEqual(building_row["property_name"], "Wohnpark Lindenhof")
        self.assertEqual(building_row["unit_count"], 3)
        self.assertEqual(building_row["room_count"], 1)

        self.assertEqual(unit_row["label"], "A-01")
        self.assertEqual(unit_row["building_name"], "Haus A")
        self.assertEqual(unit_row["property_name"], "Wohnpark Lindenhof")
        self.assertEqual(unit_row["actual_room_count"], 1)

        self.assertEqual(room_row["label"], "Wohnzimmer")
        self.assertEqual(room_row["unit_label"], "A-01")
        self.assertEqual(room_row["building_name"], "Haus A")
        self.assertEqual(room_row["property_name"], "Wohnpark Lindenhof")

        self.assertEqual(expense_row["label"], "Heizung")
        self.assertEqual(expense_row["expense_category"], "Heizung")
        self.assertEqual(expense_row["beneficiary_name"], "Stadtwerke Berlin")
        self.assertEqual(expense_row["object_type"], "property")
        self.assertNotIn("property_name", expense_row)
        self.assertTrue(overview["expense_categories"])
        self.assertIn(
            ("Heizung", "Stadtwerke Berlin"),
            {
                (category["expense_category"], category["beneficiary_name"])
                for category in overview["expense_categories"]
            },
        )

    def test_archive_and_delete_room_requires_archive_first(self) -> None:
        created = self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Archivzimmer",
            },
        )

        with self.assertRaises(ValueError) as error:
            self.registry.delete_room(created["id"])
        self.assertIn("archived", str(error.exception))

        archived = self.registry.archive_room(created["id"])
        row = self.connection.execute(
            "SELECT is_archived, archived_at FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(archived["is_archived"], 1)
        self.assertEqual(row["is_archived"], 1)
        self.assertIsNotNone(row["archived_at"])

        deleted = self.registry.delete_room(created["id"])
        remaining = self.connection.execute(
            "SELECT id FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual(deleted["id"], created["id"])
        self.assertIsNone(remaining)

    def test_restore_room_clears_archive_state(self) -> None:
        created = self.registry.create_room(
            {
                "unit_id": 1,
                "label": "Rueckholzimmer",
            },
        )

        self.registry.archive_room(created["id"])
        restored = self.registry.restore_room(created["id"])
        row = self.connection.execute(
            "SELECT is_archived, archived_at FROM rooms WHERE id = ?",
            (created["id"],),
        ).fetchone()

        self.assertEqual(restored["is_archived"], 0)
        self.assertIsNone(restored["archived_at"])
        self.assertEqual(row["is_archived"], 0)
        self.assertIsNone(row["archived_at"])

    def test_delete_building_rejects_archived_parent_with_child_units(self) -> None:
        self.registry.archive_building(1)

        with self.assertRaises(ValueError) as error:
            self.registry.delete_building(1)

        self.assertIn("dependencies", str(error.exception))


if __name__ == "__main__":
    unittest.main()

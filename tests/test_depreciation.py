from __future__ import annotations

import unittest

from easyprent_accounting.depreciation import Depreciation
from easyprent_accounting.domain import DomainError
from tests.support import in_memory_database


class DepreciationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database(seeded=False)
        organization_id = self.connection.execute(
            "INSERT INTO organizations (name, organization_type) VALUES (?, ?)",
            ("Testverwaltung", "property_management"),
        ).lastrowid
        self.property_id = self.connection.execute(
            """
            INSERT INTO properties (organization_id, name, street, city, postal_code)
            VALUES (?, ?, ?, ?, ?)
            """,
            (organization_id, "Testobjekt", "Testweg 1", "Berlin", "10115"),
        ).lastrowid
        self.connection.commit()
        self.depreciation = Depreciation(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def _asset(self, **changes: object) -> dict:
        return {
            "property_id": self.property_id,
            "asset_name": "Gebäude",
            "acquisition_cost": "500000",
            "building_share_percent": "80",
            "useful_life_years": 40,
            "placed_in_service": "2025-07-01",
            **changes,
        }

    def test_create_normalizes_values_and_lists_asset_without_method(self) -> None:
        created = self.depreciation.create_asset(
            self._asset(useful_life_years="40", placed_in_service="20250102")
        )

        self.assertEqual(40, created["useful_life_years"])
        self.assertEqual("2025-01-02", created["placed_in_service"])
        self.assertNotIn("method", created)

        stored = self.connection.execute(
            "SELECT useful_life_years, placed_in_service, method "
            "FROM depreciation_assets WHERE id = ?",
            (created["id"],),
        ).fetchone()
        self.assertEqual((40, "2025-01-02", "linear"), tuple(stored))

        listed = self.depreciation.list_assets()
        self.assertEqual([created["id"]], [asset["id"] for asset in listed])
        self.assertEqual("2025-01-02", listed[0]["placed_in_service"])
        self.assertNotIn("method", listed[0])

    def test_create_leaves_commit_and_rollback_to_caller(self) -> None:
        self.depreciation.create_asset(self._asset())

        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertEqual(
            0,
            self.connection.execute("SELECT COUNT(*) FROM depreciation_assets").fetchone()[0],
        )

    def test_invalid_values_do_not_insert_an_asset(self) -> None:
        invalid_cases = (
            ({"acquisition_cost": "Infinity"}, "invalid_money"),
            ({"building_share_percent": "101"}, "invalid_percentage"),
            ({"building_share_percent": "NaN"}, "invalid_percentage"),
        )
        for changes, expected_code in invalid_cases:
            with self.subTest(changes=changes):
                with self.assertRaises(DomainError) as caught:
                    self.depreciation.create_asset(self._asset(**changes))
                self.assertEqual(expected_code, caught.exception.code)

        for changes in (
            {"useful_life_years": 0},
            {"useful_life_years": -1},
            {"placed_in_service": "2025-02-30"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.depreciation.create_asset(self._asset(**changes))

        self.assertEqual(
            0,
            self.connection.execute("SELECT COUNT(*) FROM depreciation_assets").fetchone()[0],
        )

    def test_method_is_not_a_creation_option(self) -> None:
        for method in ("linear", "declining"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                self.depreciation.create_asset(self._asset(method=method))

        self.assertEqual(
            0,
            self.connection.execute("SELECT COUNT(*) FROM depreciation_assets").fetchone()[0],
        )

    def test_schedule_prorates_linear_depreciation_by_month(self) -> None:
        self.depreciation.create_asset(self._asset())

        schedule = self.depreciation.schedule_for_year(2025)

        self.assertEqual(2025, schedule["year"])
        self.assertEqual("5000.00", schedule["total"])
        self.assertEqual(1, len(schedule["rows"]))
        self.assertEqual(6, schedule["rows"][0]["months_in_year"])
        self.assertEqual("5000.00", schedule["rows"][0]["yearly_depreciation"])
        self.assertNotIn("method", schedule["rows"][0])

    def test_schedule_rejects_stored_non_linear_method(self) -> None:
        self.connection.execute(
            """
            INSERT INTO depreciation_assets (
                property_id, asset_name, acquisition_cost, building_share_percent,
                useful_life_years, placed_in_service, method
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (self.property_id, "Altbestand", "500000", "80", 40, "2025-07-01", "declining"),
        )

        with self.assertRaises(ValueError):
            self.depreciation.schedule_for_year(2025)
        self.assertEqual("Altbestand", self.depreciation.list_assets()[0]["asset_name"])


if __name__ == "__main__":
    unittest.main()

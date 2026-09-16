"""Behavior at the Tenancy module boundary."""

from __future__ import annotations

import unittest

from easyprent_accounting.asset_registry import AssetRegistry
from easyprent_accounting.tenancy import Tenancy
from tests.support import in_memory_database


class TenancyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.tenancy = Tenancy(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_room_assignment_derives_unit_and_normalizes_contract_period(self) -> None:
        room = AssetRegistry(self.connection).create_room(
            {"unit_id": 3, "label": "Arbeitszimmer"}
        )

        lease = self.tenancy.create_lease(
            {
                "tenant_id": 1,
                "room_id": room["id"],
                "rent_cold": "900.00",
                "additional_charges_advance": "180.00",
                "occupant_count": 1,
                "start_date": "20250101",
                "end_date": "2025-12-31",
            }
        )

        self.assertEqual((lease["room_id"], lease["unit_id"]), (room["id"], 3))
        self.assertEqual((lease["start_date"], lease["end_date"]), ("2025-01-01", "2025-12-31"))
        listed = next(
            row for row in self.tenancy.list_tenancy()["leases"] if row["id"] == lease["id"]
        )
        self.assertEqual(listed["rental_object_type"], "room")
        self.assertEqual(listed["rental_object_label"], "Arbeitszimmer (A-03)")

    def test_gnucash_advance_account_belongs_to_one_lease(self) -> None:
        first = dict(self.connection.execute("SELECT * FROM leases WHERE id = 1").fetchone())
        second = dict(self.connection.execute("SELECT * FROM leases WHERE id = 2").fetchone())
        first["gnucash_nk_account_guid"] = "nk-account"
        first["gnucash_nk_account_name"] = "Mieter:Nebenkosten"
        self.tenancy.update_lease(1, first)

        second["gnucash_nk_account_guid"] = "nk-account"
        with self.assertRaisesRegex(ValueError, "only be assigned to one lease"):
            self.tenancy.update_lease(2, second)

        listed = self.tenancy.list_tenancy()["leases"]
        self.assertEqual(listed[0]["gnucash_nk_account_guid"], "nk-account")
        self.assertIsNone(listed[1]["gnucash_nk_account_guid"])

    def test_tenant_write_can_be_rolled_back_by_caller(self) -> None:
        created = self.tenancy.create_tenant({"full_name": "Entwurf"})
        self.assertIn(created, self.tenancy.list_tenancy()["tenants"])

        self.connection.rollback()

        self.assertNotIn(created, self.tenancy.list_tenancy()["tenants"])


if __name__ == "__main__":
    unittest.main()

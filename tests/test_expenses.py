from __future__ import annotations

import unittest
from decimal import Decimal

from easyprent_accounting.expenses import Expenses
from easyprent_accounting.metering import Metering
from tests.support import in_memory_database


class ExpensesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = in_memory_database()
        self.expenses = Expenses(self.connection)

    def tearDown(self) -> None:
        self.connection.close()

    def test_category_target_recurrence_and_update_are_visible_through_module(self) -> None:
        created = self.expenses.create(
            {
                "object_type": "unit",
                "object_id": 1,
                "expense_category": "Versicherung",
                "beneficiary_name": "Versicherer",
                "amount": "366",
                "allocation_method": "area",
                "recurrence": "recurring",
                "interval": "yearly",
                "period_start": "2024-02-01",
                "period_end": "2024-02-29",
            }
        )
        self.assertEqual(created["total_amount"], "29.00")
        self.assertEqual(created["charge_type"], "yearly")
        self.assertEqual(created["expense_category"], "Versicherung")
        self.assertEqual(created["object_type"], "unit")

        updated = self.expenses.update(
            created["id"],
            {
                "object_type": "property",
                "object_id": 1,
                "expense_category": "Reinigung",
                "beneficiary_name": "Dienstleister",
                "amount": "365",
                "allocation_method": "unit_count",
                "charge_type": "one_time",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            },
        )
        self.assertEqual(updated["total_amount"], "365.00")
        listed = next(row for row in self.expenses.list_expenses()["expenses"] if row["id"] == created["id"])
        self.assertEqual((listed["expense_category"], listed["object_name"], listed["total_amount"]),
                         ("Reinigung", "Wohnpark Lindenhof", "365.00"))
        self.assertEqual(
            self.expenses.amount_for_period(listed, "2025-07-01", "2025-12-31"),
            (None, "184.00"),
        )

    def test_manual_consumption_prices_quantity_and_archive_blocks_edits(self) -> None:
        created = self.expenses.create(
            {
                "object_type": "property",
                "object_id": 1,
                "expense_category": "Wasser",
                "amount": "0.3333333333",
                "allocation_method": "occupants",
                "charge_type": "consumption",
                "consumption_unit": "m3",
                "consumption_value": "3",
                "period_start": "2025-01-01",
                "period_end": "2025-12-31",
            }
        )
        self.assertEqual(created["total_amount"], "1.00")
        self.assertEqual(created["effective_consumption_value"], "3")
        archived = self.expenses.archive(created["id"])
        self.assertEqual(archived, self.expenses.archive(created["id"]))
        with self.assertRaisesRegex(ValueError, "archived expenses cannot be edited"):
            self.expenses.update(created["id"], {})
        self.assertEqual(self.expenses.restore(created["id"])["is_archived"], 0)

    def test_deletion_requires_archive_and_no_linked_documents(self) -> None:
        created = self.expenses.create(
            {
                "object_type": "property", "object_id": 1,
                "expense_category": "Reparatur", "amount": "100",
                "allocation_method": "unit_count", "booking_date": "2025-05-01",
            }
        )
        with self.assertRaisesRegex(ValueError, "must be archived"):
            self.expenses.delete(created["id"])
        self.expenses.archive(created["id"])
        self.assertEqual(self.expenses.delete(created["id"])["deleted"], True)
        with self.assertRaisesRegex(ValueError, "expense not found"):
            self.expenses.delete(created["id"])

    def test_invalid_interval_and_non_finite_conversion_are_rejected_before_insert(self) -> None:
        base = {
            "object_type": "property", "object_id": 1,
            "expense_category": "Wasser", "amount": "2",
            "allocation_method": "occupants", "period_start": "2025-01-01",
        }
        with self.assertRaisesRegex(ValueError, "interval"):
            self.expenses.create({**base, "recurrence": "recurring", "interval": "weekly"})

        meter = Metering(self.connection).create_meter({
            "object_type": "property", "object_id": 1,
            "label": "Wasser", "meter_type": "water", "unit": "m3",
        })
        before = self.connection.execute("SELECT COUNT(*) FROM expense_items").fetchone()[0]
        with self.assertRaises(ValueError):
            self.expenses.create({
                **base, "charge_type": "consumption", "period_end": "2025-12-31",
                "meter_id": meter["id"], "conversion_factor": "NaN",
            })
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM expense_items").fetchone()[0], before)

    def test_caller_controls_transaction_rollback(self) -> None:
        created_id = None
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.connection:
                created_id = self.expenses.create({
                    "object_type": "property", "object_id": 1,
                    "expense_category": "Reparatur", "amount": "100",
                    "allocation_method": "unit_count", "booking_date": "2025-05-01",
                })["id"]
                raise RuntimeError("rollback")
        self.assertIsNotNone(created_id)
        self.assertIsNone(self.connection.execute(
            "SELECT id FROM expense_items WHERE id = ?", (created_id,)
        ).fetchone())


if __name__ == "__main__":
    unittest.main()

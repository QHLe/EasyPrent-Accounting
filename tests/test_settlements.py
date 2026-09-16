from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from easyprent_accounting.settlements import (
    ExpenseSnapshot,
    LeaseSnapshot,
    MeterReadingSnapshot,
    PaymentSnapshot,
    SettlementSnapshot,
    calculate_settlement_snapshot,
)


class SettlementSnapshotTests(unittest.TestCase):
    def test_sequential_leases_share_exact_cost_and_only_their_own_payments(self) -> None:
        snapshot = SettlementSnapshot(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            property_id=1,
            unit_id=None,
            leases=(
                LeaseSnapshot(1, "Previous", "A", 1, None, 1, Decimal("100"), None, 1, Decimal("0"), date(2025, 1, 1), date(2025, 6, 30)),
                LeaseSnapshot(2, "Next", "A", 1, None, 1, Decimal("100"), None, 1, Decimal("0"), date(2025, 7, 1), None),
            ),
            expenses=(
                ExpenseSnapshot(
                    id=1,
                    label="Annual cost",
                    category="Annual cost",
                    amount=Decimal("365"),
                    allocation_method="unit_count",
                    charge_type="one_time",
                    recurrence="one_time",
                    interval_name=None,
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 12, 31),
                    object_type="property",
                    object_id=1,
                ),
            ),
            meter_readings=(),
            payments=(
                PaymentSnapshot(1, "first", date(2025, 3, 1), Decimal("-20"), "March"),
                PaymentSnapshot(2, "second", date(2025, 9, 1), Decimal("-30"), "September"),
            ),
        )

        actual = calculate_settlement_snapshot(snapshot)

        self.assertEqual([row["allocated_costs"] for row in actual["results"]], ["181.00", "184.00"])
        self.assertEqual([row["advances_paid"] for row in actual["results"]], ["20.00", "30.00"])
        self.assertEqual(actual["totals"], {"costs": "365.00", "advances": "50.00", "balance": "315.00"})
        self.assertEqual(len(actual["results"][0]["line_items"][0]["allocation_periods"]), 1)

    def test_meter_reading_snapshot_controls_consumption_price(self) -> None:
        snapshot = SettlementSnapshot(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            property_id=1,
            unit_id=None,
            leases=(LeaseSnapshot(1, "Anna", "A", 1, None, 1, Decimal("100"), None, 1, Decimal("0"), date(2025, 1, 1), None),),
            expenses=(ExpenseSnapshot(
                id=2, label="Water", category="Water", amount=Decimal("2"),
                allocation_method="unit_count", charge_type="consumption", recurrence="one_time",
                interval_name=None, period_start=date(2025, 1, 1), period_end=date(2025, 1, 31),
                object_type="unit", object_id=1, meter_id=3, consumption_unit="m3",
                conversion_factor=Decimal("1"),
            ),),
            meter_readings=(
                MeterReadingSnapshot(3, date(2025, 1, 1), Decimal("10")),
                MeterReadingSnapshot(3, date(2025, 2, 1), Decimal("35")),
            ),
            payments=(),
        )

        actual = calculate_settlement_snapshot(snapshot)

        self.assertEqual(actual["totals"]["costs"], "50.00")
        self.assertEqual(actual["results"][0]["line_items"][0]["consumption_value"], "25")

    def test_final_calendar_day_can_be_settled(self) -> None:
        final_day = date.max
        snapshot = SettlementSnapshot(
            period_start=final_day, period_end=final_day, property_id=1, unit_id=None,
            leases=(LeaseSnapshot(1, "Anna", "A", 1, None, 1, Decimal("100"),
                                  None, 1, Decimal("0"), final_day, None),),
            expenses=(ExpenseSnapshot(
                id=1, label="Repair", category="Repair", amount=Decimal("1"),
                allocation_method="unit_count", charge_type="one_time",
                recurrence="one_time", interval_name=None,
                period_start=final_day, period_end=final_day,
                object_type="property", object_id=1,
            ),),
            meter_readings=(), payments=(),
        )

        actual = calculate_settlement_snapshot(snapshot)

        self.assertEqual(actual["totals"]["costs"], "1.00")


if __name__ == "__main__":
    unittest.main()

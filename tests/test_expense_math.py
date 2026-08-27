from __future__ import annotations

from datetime import date
from decimal import Decimal
import unittest

from src.easyprent_accounting.expense_math import (
    day_accurate_recurring_amount,
    meter_consumption_for_period,
    overlap_period,
)


class ExpenseMathTests(unittest.TestCase):
    def test_overlap_period_returns_common_range(self) -> None:
        overlap = overlap_period("2025-01-05", "2025-01-20", "2025-01-10", "2025-01-25")
        self.assertEqual(overlap, ("2025-01-10", "2025-01-20"))

    def test_overlap_period_returns_none_without_overlap(self) -> None:
        overlap = overlap_period("2025-01-01", "2025-01-10", "2025-01-11", "2025-01-20")
        self.assertIsNone(overlap)

    def test_day_accurate_monthly_amount_uses_calendar_days(self) -> None:
        amount = day_accurate_recurring_amount(
            Decimal("290"),
            "monthly",
            date(2024, 2, 10),
            date(2024, 2, 29),
        )
        self.assertEqual(amount, Decimal("200.00"))

    def test_day_accurate_yearly_amount_uses_anchor_cycle(self) -> None:
        amount = day_accurate_recurring_amount(
            Decimal("366"),
            "yearly",
            date(2024, 2, 1),
            date(2024, 2, 29),
            date(2023, 3, 1),
        )
        self.assertEqual(amount, Decimal("29.00"))

    def test_meter_consumption_for_period_uses_linear_interpolation(self) -> None:
        reading_points = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
        ]
        consumption = meter_consumption_for_period(
            reading_points,
            "2025-01-03",
            "2025-01-08",
        )
        self.assertEqual(consumption, Decimal("10"))

    def test_meter_consumption_for_period_returns_none_outside_known_range(self) -> None:
        reading_points = [
            (date(2025, 1, 1), Decimal("100")),
            (date(2025, 1, 11), Decimal("120")),
        ]
        consumption = meter_consumption_for_period(
            reading_points,
            "2024-12-31",
            "2025-01-08",
        )
        self.assertIsNone(consumption)


if __name__ == "__main__":
    unittest.main()

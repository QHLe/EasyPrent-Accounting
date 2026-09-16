from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from easyprent_accounting.domain import DomainError
from easyprent_accounting.expense_pricer import ExpensePricer, ExpensePricing


class ExpensePricerTests(unittest.TestCase):
    def test_overlap_is_inclusive_and_can_be_empty(self) -> None:
        self.assertEqual(
            ExpensePricer.overlap(
                date(2025, 1, 5), date(2025, 1, 20),
                date(2025, 1, 10), date(2025, 1, 25),
            ),
            (date(2025, 1, 10), date(2025, 1, 20)),
        )
        self.assertIsNone(
            ExpensePricer.overlap(
                date(2025, 1, 1), date(2025, 1, 10),
                date(2025, 1, 11), date(2025, 1, 20),
            )
        )

    def test_calendar_days_and_anchor_cycles(self) -> None:
        cases = (
            ("monthly", "290", date(2024, 2, 10), date(2024, 2, 10), date(2024, 2, 29), "200.00"),
            ("yearly", "366", date(2023, 3, 1), date(2024, 2, 1), date(2024, 2, 29), "29.00"),
            ("quarterly", "300", date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 31), "196.67"),
        )
        for charge_type, amount, anchor, start, end, expected in cases:
            with self.subTest(charge_type=charge_type):
                self.assertEqual(
                    ExpensePricer.price(
                        ExpensePricing(Decimal(amount), charge_type, anchor), start, end
                    ),
                    Decimal(expected),
                )

    def test_period_pricing_variants(self) -> None:
        cases = (
            ("one_time", "365", date(2024, 12, 1), date(2025, 11, 30), date(2025, 1, 1), date(2025, 12, 31), None, "334.00"),
            ("monthly", "31", date(2025, 1, 16), None, date(2025, 1, 1), date(2025, 1, 31), None, "16.00"),
            ("quarterly", "90", date(2025, 1, 1), None, date(2025, 2, 1), date(2025, 2, 28), None, "28.00"),
            ("yearly", "366", date(2024, 1, 1), None, date(2024, 2, 1), date(2024, 2, 29), None, "29.00"),
            ("yearly", "1200", date(2023, 12, 1), date(2024, 11, 30), date(2023, 12, 1), date(2024, 11, 30), None, "1200.00"),
            ("consumption", "0.3333333333", date(2025, 1, 1), date(2025, 12, 31), date(2025, 1, 1), date(2025, 12, 31), "3", "1.00"),
        )
        for charge_type, amount, start, end, period_start, period_end, quantity, expected in cases:
            with self.subTest(charge_type=charge_type, start=start, period_start=period_start):
                actual = ExpensePricer.price(
                    ExpensePricing(
                        amount=Decimal(amount),
                        charge_type=charge_type,
                        expense_start=start,
                        expense_end=end,
                        consumption_value=Decimal(quantity) if quantity is not None else None,
                    ),
                    period_start,
                    period_end,
                )
                self.assertEqual(actual, Decimal(expected))

    def test_missing_consumption_is_unpriced_and_outside_period_is_zero(self) -> None:
        expense = ExpensePricing(Decimal("2"), "consumption", date(2025, 1, 1), date(2025, 12, 31))
        self.assertIsNone(ExpensePricer.price(expense, date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual(ExpensePricer.price(expense, date(2026, 1, 1), date(2026, 12, 31)), Decimal("0"))

    def test_future_open_ended_recurring_cost_is_zero_before_start(self) -> None:
        expense = ExpensePricing(Decimal("31"), "monthly", date(2026, 1, 16))
        self.assertEqual(
            ExpensePricer.price(expense, date(2025, 1, 1), date(2025, 12, 31)),
            Decimal("0"),
        )

    def test_reversed_billing_period_is_domain_error(self) -> None:
        expense = ExpensePricing(Decimal("100"), "one_time")
        with self.assertRaises(DomainError) as caught:
            ExpensePricer.price(expense, date(2025, 12, 31), date(2025, 1, 1))
        self.assertEqual(caught.exception.code, "invalid_date_range")


if __name__ == "__main__":
    unittest.main()

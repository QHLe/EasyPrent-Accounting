import datetime
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal

from easyprent_accounting.domain import (
    Date,
    DateRange,
    DomainError,
    Money,
    Percentage,
)


class DomainErrorTests(unittest.TestCase):
    def test_stores_stable_code_and_human_readable_reason(self) -> None:
        error = DomainError("invalid_value", "The value is not valid.")

        self.assertEqual("invalid_value", error.code)
        self.assertEqual("The value is not valid.", error.reason)
        self.assertEqual("invalid_value: The value is not valid.", str(error))
        self.assertIsInstance(error, ValueError)


class MoneyTests(unittest.TestCase):
    def test_preserves_decimal_value_without_rounding(self) -> None:
        value = Decimal("-0.123456789100")

        money = Money(value)

        self.assertEqual(value.as_tuple(), money.amount.as_tuple())

    def test_rejects_non_decimal_values(self) -> None:
        with self.assertRaises(DomainError) as caught:
            Money(12.34)  # type: ignore[arg-type]

        self.assertEqual("invalid_money", caught.exception.code)

    def test_rejects_non_finite_values(self) -> None:
        for value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    Money(value)
                self.assertEqual("invalid_money", caught.exception.code)

    def test_is_an_immutable_hashable_value(self) -> None:
        money = Money(Decimal("12.50"))

        self.assertEqual(money, Money(Decimal("12.50")))
        self.assertEqual({money}, {Money(Decimal("12.50"))})
        with self.assertRaises(FrozenInstanceError):
            money.amount = Decimal("13.00")  # type: ignore[misc]


class PercentageTests(unittest.TestCase):
    def test_accepts_inclusive_domain_boundaries(self) -> None:
        self.assertEqual(Decimal("0"), Percentage(Decimal("0")).value)
        self.assertEqual(Decimal("100"), Percentage(Decimal("100")).value)

    def test_preserves_decimal_value_without_rounding(self) -> None:
        value = Decimal("33.3333333333")

        percentage = Percentage(value)

        self.assertEqual(value.as_tuple(), percentage.value.as_tuple())

    def test_rejects_values_outside_zero_to_one_hundred(self) -> None:
        for value in (Decimal("-0.01"), Decimal("100.01")):
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    Percentage(value)
                self.assertEqual("invalid_percentage", caught.exception.code)

    def test_rejects_non_decimal_and_non_finite_values(self) -> None:
        for value in ("50", Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    Percentage(value)  # type: ignore[arg-type]
                self.assertEqual("invalid_percentage", caught.exception.code)


class DateTests(unittest.TestCase):
    def test_wraps_a_calendar_date(self) -> None:
        value = datetime.date(2025, 2, 28)

        domain_date = Date(value)

        self.assertEqual(value, domain_date.value)
        self.assertEqual("2025-02-28", domain_date.isoformat())

    def test_rejects_datetime_and_non_date_values(self) -> None:
        values = (datetime.datetime(2025, 2, 28, 12, 30), "2025-02-28")
        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    Date(value)  # type: ignore[arg-type]
                self.assertEqual("invalid_date", caught.exception.code)

    def test_from_isoformat_maps_malformed_input_to_a_domain_error(self) -> None:
        self.assertEqual(
            Date(datetime.date(2024, 2, 29)),
            Date.from_isoformat("2024-02-29"),
        )

        for value in ("2025-02-29", "not-a-date", 20250228):
            with self.subTest(value=value):
                with self.assertRaises(DomainError) as caught:
                    Date.from_isoformat(value)  # type: ignore[arg-type]
                self.assertEqual("invalid_date", caught.exception.code)

    def test_is_an_immutable_ordered_value(self) -> None:
        earlier = Date(datetime.date(2025, 1, 1))
        later = Date(datetime.date(2025, 1, 2))

        self.assertLess(earlier, later)
        self.assertEqual({earlier}, {Date(datetime.date(2025, 1, 1))})
        with self.assertRaises(FrozenInstanceError):
            earlier.value = datetime.date(2026, 1, 1)  # type: ignore[misc]


class DateRangeTests(unittest.TestCase):
    def test_stores_inclusive_start_and_end(self) -> None:
        start = Date(datetime.date(2025, 1, 1))
        end = Date(datetime.date(2025, 12, 31))

        date_range = DateRange(start, end)

        self.assertEqual(start, date_range.start)
        self.assertEqual(end, date_range.end)

    def test_rejects_end_before_start_with_clear_error(self) -> None:
        start = Date(datetime.date(2025, 1, 1))
        end = Date(datetime.date(2024, 12, 31))

        with self.assertRaises(DomainError) as caught:
            DateRange(start, end)

        self.assertEqual("invalid_date_range", caught.exception.code)
        self.assertEqual("End date cannot be before start date.", caught.exception.reason)

    def test_rejects_boundaries_that_are_not_domain_dates(self) -> None:
        raw_date = datetime.date(2025, 1, 1)

        with self.assertRaises(DomainError) as caught:
            DateRange(raw_date, raw_date)  # type: ignore[arg-type]

        self.assertEqual("invalid_date_range", caught.exception.code)

    def test_allows_same_start_and_end(self) -> None:
        date = Date(datetime.date(2025, 1, 1))

        date_range = DateRange(date, date)

        self.assertEqual(date, date_range.start)
        self.assertEqual(date, date_range.end)

    def test_is_immutable_and_safe_to_use_as_a_hash_key(self) -> None:
        date_range = DateRange(
            Date(datetime.date(2025, 1, 1)),
            Date(datetime.date(2025, 12, 31)),
        )
        values = {date_range}

        self.assertIn(
            DateRange(
                Date(datetime.date(2025, 1, 1)),
                Date(datetime.date(2025, 12, 31)),
            ),
            values,
        )
        with self.assertRaises(FrozenInstanceError):
            date_range.end = Date(datetime.date(2026, 12, 31))  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()

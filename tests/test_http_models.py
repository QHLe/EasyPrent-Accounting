"""Public validation and JSON contracts for shared HTTP payloads."""

from __future__ import annotations

import datetime
import unittest
from decimal import Decimal

from pydantic import ValidationError

from easyprent_accounting.http_models import (
    DateRangeModel,
    ErrorDetail,
    ErrorResponse,
    IdModel,
    MoneyModel,
)


class IdModelTests(unittest.TestCase):
    def test_accepts_positive_integer_id(self) -> None:
        self.assertEqual(IdModel.model_validate({"id": 7}).id, 7)

    def test_rejects_non_positive_or_coerced_ids(self) -> None:
        for value in (0, -1, True, 1.0, "1"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                IdModel.model_validate({"id": value})


class MoneyModelTests(unittest.TestCase):
    def test_preserves_decimal_precision_as_a_json_string(self) -> None:
        amount = MoneyModel.model_validate({"amount": "-123456789.0010"})

        self.assertEqual(amount.amount, Decimal("-123456789.0010"))
        self.assertEqual(amount.model_dump(mode="json"), {"amount": "-123456789.0010"})
        self.assertEqual(amount.model_dump_json(), '{"amount":"-123456789.0010"}')
        self.assertEqual(
            MoneyModel.model_json_schema(mode="serialization")["properties"]["amount"]["type"],
            "string",
        )
        self.assertEqual(
            MoneyModel.model_json_schema(mode="validation")["properties"]["amount"]["type"],
            "string",
        )

    def test_accepts_decimal_from_backend(self) -> None:
        amount = MoneyModel(amount=Decimal("0.00"))

        self.assertEqual(amount.model_dump(mode="json"), {"amount": "0.00"})

    def test_rejects_float_non_finite_and_invalid_amounts(self) -> None:
        for value in (0.1, 1, "NaN", "Infinity", "not-money"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                MoneyModel.model_validate({"amount": value})


class DateRangeModelTests(unittest.TestCase):
    def test_accepts_inclusive_single_day_period(self) -> None:
        period = DateRangeModel.model_validate(
            {"start": "2024-02-29", "end": "2024-02-29"}
        )

        self.assertEqual(period.start, datetime.date(2024, 2, 29))
        self.assertEqual(
            period.model_dump(mode="json"),
            {"start": "2024-02-29", "end": "2024-02-29"},
        )

    def test_rejects_reversed_or_non_calendar_boundaries(self) -> None:
        for start, end in (
            ("2025-01-02", "2025-01-01"),
            ("2025-02-29", "2025-03-01"),
            ("2025-01-01T00:00:00", "2025-01-02"),
            (datetime.datetime(2025, 1, 1), datetime.date(2025, 1, 2)),
            (1735689600, "2025-01-02"),
        ):
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                DateRangeModel.model_validate({"start": start, "end": end})


class ErrorResponseTests(unittest.TestCase):
    def test_serializes_common_error_envelope(self) -> None:
        response = ErrorResponse(
            error=ErrorDetail(code="invalid_date_range", reason="End date is too early.")
        )

        self.assertEqual(
            response.model_dump(mode="json"),
            {"error": {"code": "invalid_date_range", "reason": "End date is too early."}},
        )

    def test_rejects_unknown_fields_and_empty_error_details(self) -> None:
        for payload in (
            {"error": {"code": "", "reason": "Invalid."}},
            {"error": {"code": "invalid", "reason": ""}},
            {"error": {"code": "invalid", "reason": "Invalid.", "extra": 1}},
            {"error": {"code": "invalid", "reason": "Invalid."}, "extra": 1},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ErrorResponse.model_validate(payload)


if __name__ == "__main__":
    unittest.main()

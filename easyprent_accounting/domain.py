from __future__ import annotations

import datetime
from dataclasses import dataclass
from decimal import Decimal


class DomainError(ValueError):
    """A domain rule violation with a stable machine-readable code."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(f"{code}: {reason}")
        self.code = code
        self.reason = reason


def _require_finite_decimal(value: object, code: str, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise DomainError(code, f"{name} must be a finite Decimal.")
    return value


@dataclass(frozen=True, order=True, slots=True)
class Money:
    """A finite monetary amount that retains the supplied decimal precision."""

    amount: Decimal

    def __post_init__(self) -> None:
        _require_finite_decimal(self.amount, "invalid_money", "Money")


@dataclass(frozen=True, order=True, slots=True)
class Percentage:
    """A percentage from zero through one hundred, without implicit rounding."""

    value: Decimal

    def __post_init__(self) -> None:
        value = _require_finite_decimal(
            self.value,
            "invalid_percentage",
            "Percentage",
        )
        if value < Decimal("0") or value > Decimal("100"):
            raise DomainError(
                "invalid_percentage",
                "Percentage must be between 0 and 100 inclusive.",
            )


@dataclass(frozen=True, order=True, slots=True)
class Date:
    """A calendar date without a time or timezone."""

    value: datetime.date

    def __post_init__(self) -> None:
        if isinstance(self.value, datetime.datetime) or not isinstance(
            self.value,
            datetime.date,
        ):
            raise DomainError(
                "invalid_date",
                "Date must be a calendar date without a time.",
            )

    @classmethod
    def from_isoformat(cls, value: str) -> Date:
        if not isinstance(value, str):
            raise DomainError(
                "invalid_date",
                "Date must be a valid ISO 8601 date.",
            )
        try:
            parsed = datetime.date.fromisoformat(value)
        except ValueError as error:
            raise DomainError(
                "invalid_date",
                "Date must be a valid ISO 8601 date.",
            ) from error
        return cls(parsed)

    def isoformat(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True, slots=True)
class DateRange:
    """A period bounded by a start and end date (inclusive)."""

    start: Date
    end: Date

    def __post_init__(self) -> None:
        if not isinstance(self.start, Date) or not isinstance(self.end, Date):
            raise DomainError(
                "invalid_date_range",
                "Date range boundaries must be domain dates.",
            )
        if self.end < self.start:
            raise DomainError(
                "invalid_date_range",
                "End date cannot be before start date.",
            )

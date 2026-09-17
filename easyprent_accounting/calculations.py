from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .domain import Date as DomainDate
from .domain import Money


TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return Money(value).amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def parse_date(value: str) -> date:
    return DomainDate.from_isoformat(value).value

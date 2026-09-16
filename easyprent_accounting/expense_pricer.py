"""Pure, decimal-exact period pricing for every expense type."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from .domain import Date as DomainDate
from .domain import DateRange, DomainError, Money


CENT = Decimal("0.01")


def _rounded(value: Decimal) -> Decimal:
    return Money(value).amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _add_months(day: date, months: int) -> date:
    month_index = day.year * 12 + day.month - 1 + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


@dataclass(frozen=True, slots=True)
class ExpensePricing:
    amount: Decimal
    charge_type: str
    expense_start: date | None = None
    expense_end: date | None = None
    consumption_value: Decimal | None = None


class ExpensePricer:
    """Calculate the value of an expense in an inclusive billing period."""

    @staticmethod
    def overlap(
        first_start: date, first_end: date, second_start: date, second_end: date
    ) -> tuple[date, date] | None:
        DateRange(DomainDate(first_start), DomainDate(first_end))
        DateRange(DomainDate(second_start), DomainDate(second_end))
        start = max(first_start, second_start)
        end = min(first_end, second_end)
        return (start, end) if start <= end else None

    @staticmethod
    def amount_for_period(
        *,
        amount: Decimal,
        charge_type: str,
        expense_start: date | None,
        expense_end: date | None,
        period_start: date,
        period_end: date,
        consumption_value: Decimal | None = None,
    ) -> Decimal | None:
        return ExpensePricer.price(
            ExpensePricing(amount, charge_type, expense_start, expense_end, consumption_value),
            period_start,
            period_end,
        )

    @staticmethod
    def price(expense: ExpensePricing, period_start: date, period_end: date) -> Decimal | None:
        DateRange(DomainDate(period_start), DomainDate(period_end))
        amount = Money(expense.amount).amount
        if expense.charge_type not in {"one_time", "monthly", "quarterly", "yearly", "consumption"}:
            raise DomainError("invalid_charge_type", "Unsupported expense charge type.")

        expense_start = expense.expense_start or period_start
        expense_end = expense.expense_end or (
            date.max
            if expense.expense_start is not None
            and expense.charge_type in {"monthly", "quarterly", "yearly"}
            else period_end
        )
        DateRange(DomainDate(expense_start), DomainDate(expense_end))
        overlap = ExpensePricer.overlap(expense_start, expense_end, period_start, period_end)
        if overlap is None:
            return Decimal("0")
        overlap_start, overlap_end = overlap

        if expense.charge_type == "consumption":
            if expense.consumption_value is None:
                return None
            quantity = Money(expense.consumption_value).amount
            return _rounded(amount * quantity)

        if expense.charge_type == "one_time":
            total_days = Decimal((expense_end - expense_start).days + 1)
            overlap_days = Decimal((overlap_end - overlap_start).days + 1)
            return _rounded(amount * overlap_days / total_days)

        if expense.charge_type == "monthly":
            total = Decimal("0")
            current = overlap_start
            while current <= overlap_end:
                days_in_month = monthrange(current.year, current.month)[1]
                segment_end = min(date(current.year, current.month, days_in_month), overlap_end)
                total += amount * Decimal((segment_end - current).days + 1) / Decimal(days_in_month)
                if segment_end == overlap_end:
                    break
                current = segment_end + timedelta(days=1)
            return _rounded(total)

        cycle_months = 3 if expense.charge_type == "quarterly" else 12
        cycle_start = expense_start
        while _add_months(cycle_start, cycle_months) <= overlap_start:
            cycle_start = _add_months(cycle_start, cycle_months)
        total = Decimal("0")
        current = overlap_start
        while current <= overlap_end:
            next_cycle = _add_months(cycle_start, cycle_months)
            cycle_end = next_cycle - timedelta(days=1)
            segment_end = min(cycle_end, overlap_end)
            active_days = Decimal((segment_end - current).days + 1)
            cycle_days = Decimal((next_cycle - cycle_start).days)
            total += amount * active_days / cycle_days
            if segment_end == overlap_end:
                break
            current = segment_end + timedelta(days=1)
            cycle_start = next_cycle
        return _rounded(total)

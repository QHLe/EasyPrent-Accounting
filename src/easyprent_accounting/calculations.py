from __future__ import annotations

from dataclasses import dataclass
from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def overlap_months(start_a: date, end_a: date, start_b: date, end_b: date) -> int:
    current = date(max(start_a.year, start_b.year), max(start_a.month, start_b.month), 1)
    limit = date(min(end_a.year, end_b.year), min(end_a.month, end_b.month), 1)
    if current > limit:
        return 0

    months = 0
    while current <= limit:
        months += 1
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def yearly_occurrences(start_a: date, end_a: date, start_b: date, end_b: date) -> int:
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    if overlap_start > overlap_end:
        return 0

    occurrences = 0
    year = start_a.year
    while True:
        occurrence = date(year, start_a.month, start_a.day)
        if occurrence > end_a or occurrence > overlap_end:
            break
        if occurrence >= overlap_start:
            occurrences += 1
        year += 1
    return occurrences


def quarterly_occurrences(start_a: date, end_a: date, start_b: date, end_b: date) -> int:
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    if overlap_start > overlap_end:
        return 0

    occurrences = 0
    occurrence = start_a
    while occurrence <= end_a and occurrence <= overlap_end:
        if occurrence >= overlap_start:
            occurrences += 1
        target_month_index = occurrence.year * 12 + occurrence.month - 1 + 3
        target_year, target_month_zero_based = divmod(target_month_index, 12)
        target_month = target_month_zero_based + 1
        occurrence = date(
            target_year,
            target_month,
            min(occurrence.day, monthrange(target_year, target_month)[1]),
        )
    return occurrences


def _add_months(source_date: date, month_delta: int) -> date:
    target_month_index = source_date.year * 12 + source_date.month - 1 + month_delta
    target_year, target_month_zero_based = divmod(target_month_index, 12)
    target_month = target_month_zero_based + 1
    return date(target_year, target_month, min(source_date.day, monthrange(target_year, target_month)[1]))


def _day_accurate_open_ended_recurring_amount(
    amount: Decimal,
    charge_type: str,
    overlap_start: date,
    overlap_end: date,
    anchor_start: date,
) -> Decimal:
    if charge_type == "monthly":
        total = Decimal("0")
        current_day = overlap_start
        while current_day <= overlap_end:
            month_end = date(
                current_day.year,
                current_day.month,
                monthrange(current_day.year, current_day.month)[1],
            )
            segment_end = min(month_end, overlap_end)
            active_days = (segment_end - current_day).days + 1
            total += amount * Decimal(active_days) / Decimal(month_end.day)
            current_day = date.fromordinal(segment_end.toordinal() + 1)
        return quantize_money(total)

    cycle_months = 3 if charge_type == "quarterly" else 12
    cycle_start = anchor_start
    while _add_months(cycle_start, cycle_months) <= overlap_start:
        cycle_start = _add_months(cycle_start, cycle_months)

    total = Decimal("0")
    current_day = overlap_start
    while current_day <= overlap_end:
        next_cycle_start = _add_months(cycle_start, cycle_months)
        cycle_end = date.fromordinal(next_cycle_start.toordinal() - 1)
        segment_end = min(cycle_end, overlap_end)
        active_days = (segment_end - current_day).days + 1
        cycle_days = (cycle_end - cycle_start).days + 1
        total += amount * Decimal(active_days) / Decimal(cycle_days)
        current_day = date.fromordinal(segment_end.toordinal() + 1)
        cycle_start = next_cycle_start
    return quantize_money(total)


@dataclass(slots=True)
class SettlementLease:
    lease_id: int
    tenant_name: str
    unit_label: str
    unit_area_sqm: Decimal
    occupant_count: int
    additional_charges_advance: Decimal
    lease_start: date
    lease_end: date | None


@dataclass(slots=True)
class SettlementExpense:
    label: str
    amount: Decimal
    allocation_method: str
    charge_type: str = "one_time"
    recurrence: str = "one_time"
    interval_name: str | None = None
    expense_start: date | None = None
    expense_end: date | None = None
    consumption_unit: str | None = None
    consumption_value: Decimal | None = None


def expense_amount_for_period(expense: SettlementExpense, period_start: date, period_end: date) -> Decimal:
    expense_start = expense.expense_start or period_start
    expense_end = expense.expense_end or period_end
    if expense_end < period_start or expense_start > period_end:
        return Decimal("0")

    if expense.charge_type == "consumption":
        if expense.consumption_value is None:
            return Decimal("0")
        return quantize_money(expense.amount * expense.consumption_value)
    if expense_end.year == 9999 and expense.charge_type in {"monthly", "quarterly", "yearly"}:
        overlap_start = max(expense_start, period_start)
        overlap_end = min(expense_end, period_end)
        return _day_accurate_open_ended_recurring_amount(
            expense.amount,
            expense.charge_type,
            overlap_start,
            overlap_end,
            expense_start,
        )
    if expense.charge_type == "monthly":
        active_months = overlap_months(expense_start, expense_end, period_start, period_end)
        return quantize_money(expense.amount * Decimal(active_months))
    if expense.charge_type == "yearly":
        occurrences = yearly_occurrences(expense_start, expense_end, period_start, period_end)
        return quantize_money(expense.amount * Decimal(occurrences))
    if expense.charge_type == "quarterly":
        occurrences = quarterly_occurrences(expense_start, expense_end, period_start, period_end)
        return quantize_money(expense.amount * Decimal(occurrences))

    return quantize_money(expense.amount)


def calculate_settlement(
    leases: list[SettlementLease],
    expenses: list[SettlementExpense],
    period_start: date,
    period_end: date,
) -> dict:
    active_leases = []
    for lease in leases:
        lease_end = lease.lease_end or period_end
        if lease.lease_start <= period_end and lease_end >= period_start:
            active_leases.append(lease)

    results = {
        lease.lease_id: {
            "lease_id": lease.lease_id,
            "tenant_name": lease.tenant_name,
            "unit_label": lease.unit_label,
            "allocated_costs": Decimal("0"),
            "advances_paid": Decimal("0"),
            "balance": Decimal("0"),
            "line_items": [],
        }
        for lease in active_leases
    }

    if not active_leases:
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "results": [],
            "totals": {"costs": "0.00", "advances": "0.00", "balance": "0.00"},
        }

    totals_by_method = {
        "area": sum((lease.unit_area_sqm for lease in active_leases), start=Decimal("0")),
        "unit_count": Decimal(len(active_leases)),
        "occupants": Decimal(sum(lease.occupant_count for lease in active_leases)),
    }

    for expense in expenses:
        effective_amount = expense_amount_for_period(expense, period_start, period_end)
        if effective_amount <= 0:
            continue
        basis_total = totals_by_method.get(expense.allocation_method, Decimal("0"))
        if basis_total <= 0:
            continue
        for lease in active_leases:
            if expense.allocation_method == "area":
                basis_value = lease.unit_area_sqm
            elif expense.allocation_method == "occupants":
                basis_value = Decimal(lease.occupant_count)
            else:
                basis_value = Decimal("1")

            share = quantize_money(effective_amount * basis_value / basis_total)
            result = results[lease.lease_id]
            result["allocated_costs"] += share
            line_item = {
                "label": expense.label,
                "allocation_method": expense.allocation_method,
                "charge_type": expense.charge_type,
                "recurrence": expense.recurrence,
                "interval_name": expense.interval_name,
                "share": f"{share:.2f}",
            }
            if expense.consumption_unit:
                line_item["consumption_unit"] = expense.consumption_unit
            if expense.consumption_value is not None:
                line_item["consumption_value"] = str(expense.consumption_value)
            result["line_items"].append(line_item)

    for lease in active_leases:
        lease_end = lease.lease_end or period_end
        months = overlap_months(lease.lease_start, lease_end, period_start, period_end)
        advances = quantize_money(lease.additional_charges_advance * Decimal(months))
        result = results[lease.lease_id]
        result["allocated_costs"] = quantize_money(result["allocated_costs"])
        result["advances_paid"] = advances
        result["balance"] = quantize_money(result["allocated_costs"] - advances)

    total_costs = Decimal("0")
    total_advances = Decimal("0")
    total_balance = Decimal("0")
    serialized = []
    for lease_id in sorted(results):
        item = results[lease_id]
        total_costs += item["allocated_costs"]
        total_advances += item["advances_paid"]
        total_balance += item["balance"]
        serialized.append(
            {
                **item,
                "allocated_costs": f"{item['allocated_costs']:.2f}",
                "advances_paid": f"{item['advances_paid']:.2f}",
                "balance": f"{item['balance']:.2f}",
            }
        )

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "results": serialized,
        "totals": {
            "costs": f"{quantize_money(total_costs):.2f}",
            "advances": f"{quantize_money(total_advances):.2f}",
            "balance": f"{quantize_money(total_balance):.2f}",
        },
    }


def calculate_depreciation_schedule(assets: list[dict], year: int) -> dict:
    rows = []
    total = Decimal("0")
    for asset in assets:
        start_date = parse_date(asset["placed_in_service"])
        useful_life_years = Decimal(str(asset["useful_life_years"]))
        acquisition_cost = Decimal(str(asset["acquisition_cost"]))
        building_share = Decimal(str(asset["building_share_percent"])) / Decimal("100")
        depreciable_basis = acquisition_cost * building_share
        yearly_value = depreciable_basis / useful_life_years

        months_in_year = 0
        for month in range(1, 13):
            month_start = date(year, month, 1)
            if month < 12:
                month_end = date(year, month + 1, 1)
            else:
                month_end = date(year + 1, 1, 1)
            if month_end <= start_date.replace(day=1):
                continue
            elapsed_years = (month_start.year - start_date.year) + (
                (month_start.month - start_date.month) / 12
            )
            if elapsed_years < 0 or elapsed_years >= float(useful_life_years):
                continue
            months_in_year += 1

        yearly_depreciation = quantize_money(yearly_value / Decimal("12") * Decimal(months_in_year))
        total += yearly_depreciation
        rows.append(
            {
                "asset_name": asset["asset_name"],
                "placed_in_service": asset["placed_in_service"],
                "depreciable_basis": f"{quantize_money(depreciable_basis):.2f}",
                "useful_life_years": asset["useful_life_years"],
                "method": asset["method"],
                "months_in_year": months_in_year,
                "yearly_depreciation": f"{yearly_depreciation:.2f}",
            }
        )

    return {"year": year, "rows": rows, "total": f"{quantize_money(total):.2f}"}

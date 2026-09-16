from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .domain import Date as DomainDate
from .domain import Money, Percentage


TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return Money(value).amount.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def parse_date(value: str) -> date:
    return DomainDate.from_isoformat(value).value


def calculate_depreciation_schedule(assets: list[dict], year: int) -> dict:
    rows = []
    total = Decimal("0")
    for asset in assets:
        start_date = parse_date(asset["placed_in_service"])
        useful_life_years = Decimal(str(asset["useful_life_years"]))
        acquisition_cost = Money(Decimal(str(asset["acquisition_cost"]))).amount
        building_share_percentage = Percentage(
            Decimal(str(asset["building_share_percent"]))
        )
        building_share = building_share_percentage.value / Decimal("100")
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

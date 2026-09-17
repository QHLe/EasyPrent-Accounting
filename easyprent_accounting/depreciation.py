"""Linear depreciation assets and yearly schedules."""

from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation

from .calculations import parse_date, quantize_money
from .domain import Money, Percentage


def _required_decimal(value: object, name: str) -> Decimal:
    if value in (None, ""):
        raise ValueError(f"{name} is required")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error


def _required_int(value: object, name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{name} is required")
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be an integer") from error


def _required_string(value: object, name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{name} is required")
    return str(value)


class Depreciation:
    """Persist linear depreciation assets and calculate their yearly values."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def create_asset(self, payload: dict) -> dict:
        if "method" in payload:
            raise ValueError("depreciation method is not configurable")
        acquisition_cost = Money(
            _required_decimal(payload.get("acquisition_cost"), "acquisition_cost")
        ).amount
        building_share_percent = Percentage(
            _required_decimal(payload.get("building_share_percent"), "building_share_percent")
        ).value
        useful_life_years = _required_int(payload.get("useful_life_years"), "useful_life_years")
        if useful_life_years < 1:
            raise ValueError("useful_life_years must be at least 1")
        placed_in_service = parse_date(
            _required_string(payload.get("placed_in_service"), "placed_in_service")
        ).isoformat()
        # The frozen Legacy and v1 schemas require this fixed storage marker.
        cursor = self.connection.execute(
            """
            INSERT INTO depreciation_assets (
                property_id, asset_name, acquisition_cost, building_share_percent,
                useful_life_years, placed_in_service, method
            ) VALUES (?, ?, ?, ?, ?, ?, 'linear')
            """,
            (
                payload["property_id"],
                payload["asset_name"],
                str(acquisition_cost),
                str(building_share_percent),
                useful_life_years,
                placed_in_service,
            ),
        )
        return {
            "id": cursor.lastrowid,
            "property_id": payload["property_id"],
            "asset_name": payload["asset_name"],
            "acquisition_cost": str(acquisition_cost),
            "building_share_percent": str(building_share_percent),
            "useful_life_years": useful_life_years,
            "placed_in_service": placed_in_service,
        }

    def list_assets(self) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT id, property_id, asset_name, acquisition_cost,
                   building_share_percent, useful_life_years, placed_in_service
            FROM depreciation_assets ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def schedule_for_year(self, year: int) -> dict:
        unsupported = self.connection.execute(
            "SELECT 1 FROM depreciation_assets WHERE method != 'linear' LIMIT 1"
        ).fetchone()
        if unsupported is not None:
            raise ValueError("only linear depreciation is supported")
        rows = []
        total = Decimal("0")
        for asset in self.list_assets():
            start_date = parse_date(asset["placed_in_service"])
            useful_life_years = Decimal(str(asset["useful_life_years"]))
            acquisition_cost = Money(Decimal(str(asset["acquisition_cost"]))).amount
            building_share = Percentage(
                Decimal(str(asset["building_share_percent"]))
            ).value / Decimal("100")
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

            yearly_depreciation = quantize_money(
                yearly_value / Decimal("12") * Decimal(months_in_year)
            )
            total += yearly_depreciation
            rows.append(
                {
                    "asset_name": asset["asset_name"],
                    "placed_in_service": asset["placed_in_service"],
                    "depreciable_basis": f"{quantize_money(depreciable_basis):.2f}",
                    "useful_life_years": asset["useful_life_years"],
                    "months_in_year": months_in_year,
                    "yearly_depreciation": f"{yearly_depreciation:.2f}",
                }
            )

        return {"year": year, "rows": rows, "total": f"{quantize_money(total):.2f}"}

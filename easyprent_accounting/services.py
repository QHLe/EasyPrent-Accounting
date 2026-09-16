from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal

from .asset_registry import AssetRegistry
from .metering import Metering
from .expenses import Expenses
from .domain import Money, Percentage
from .tenancy import Tenancy
from .calculations import (
    calculate_depreciation_schedule,
    parse_date,
)


def _parse_decimal(value: object, field_name: str) -> Decimal:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return Decimal(str(value))
    except Exception as error:  # pragma: no cover - Decimal raises multiple subclasses
        raise ValueError(f"{field_name} must be numeric") from error


def _parse_int(value: object, field_name: str) -> int:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    try:
        return int(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field_name} must be an integer") from error


def _require_payload_value(payload: dict, field_name: str) -> str:
    value = payload.get(field_name)
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)


def _row_dicts(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(row) for row in rows]


def health_status() -> dict:
    return {
        "status": "ok",
        "reachable": True,
        "checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
    }


def list_overview(connection: sqlite3.Connection) -> dict:
    assets = AssetRegistry(connection).list_assets()
    properties = assets["properties"]
    buildings = assets["buildings"]
    units = assets["units"]
    rooms = assets["rooms"]
    tenancy = Tenancy(connection).list_tenancy()
    tenants = tenancy["tenants"]
    leases = tenancy["leases"]
    expense_data = Expenses(connection).list_expenses()
    expenses = expense_data["expenses"]
    expense_categories = expense_data["expense_categories"]
    meter_data = Metering(connection).list_meters()
    meters = meter_data["meters"]
    meter_readings = meter_data["meter_readings"]
    depreciation_assets = _row_dicts(
        connection.execute("SELECT * FROM depreciation_assets ORDER BY id").fetchall()
    )
    users = _row_dicts(
        connection.execute(
            """
            SELECT u.full_name, u.email, m.role, o.name AS organization_name
            FROM memberships m
            JOIN users u ON u.id = m.user_id
            JOIN organizations o ON o.id = m.organization_id
            ORDER BY u.id
            """
        ).fetchall()
    )

    return {
        "summary": {
            "properties": len(properties),
            "buildings": len(buildings),
            "units": len(units),
            "rooms": len(rooms),
            "meters": len(meters),
            "tenants": len(tenants),
            "leases": len(leases),
            "expenses": len(expenses),
            "depreciation_assets": len(depreciation_assets),
        },
        "roles": users,
        "properties": properties,
        "buildings": buildings,
        "units": units,
        "rooms": rooms,
        "meters": meters,
        "meter_readings": meter_readings,
        "tenants": tenants,
        "leases": leases,
        "expenses": expenses,
        "expense_categories": expense_categories,
        "depreciation_assets": depreciation_assets,
    }


def create_depreciation_asset(connection: sqlite3.Connection, payload: dict) -> dict:
    acquisition_cost = Money(
        _parse_decimal(payload.get("acquisition_cost"), "acquisition_cost")
    ).amount
    building_share_percent = Percentage(
        _parse_decimal(
            payload.get("building_share_percent"),
            "building_share_percent",
        )
    ).value
    useful_life_years = _parse_int(payload.get("useful_life_years"), "useful_life_years")
    if useful_life_years < 1:
        raise ValueError("useful_life_years must be at least 1")
    placed_in_service = parse_date(
        _require_payload_value(payload, "placed_in_service")
    ).isoformat()
    cursor = connection.execute(
        """
        INSERT INTO depreciation_assets (
            property_id, asset_name, acquisition_cost, building_share_percent,
            useful_life_years, placed_in_service, method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["property_id"],
            payload["asset_name"],
            str(acquisition_cost),
            str(building_share_percent),
            useful_life_years,
            placed_in_service,
            payload.get("method", "linear"),
        ),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        **payload,
        "useful_life_years": useful_life_years,
        "placed_in_service": placed_in_service,
    }


def depreciation_schedule_for_year(connection: sqlite3.Connection, year: int) -> dict:
    assets = _row_dicts(connection.execute("SELECT * FROM depreciation_assets ORDER BY id").fetchall())
    return calculate_depreciation_schedule(assets, year)
